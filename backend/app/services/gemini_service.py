import json
import hashlib
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import List, Dict, Any, Optional
from google import genai
from google.genai import types
from backend.app.config import (
    DISABLE_GEMINI, GEMINI_API_KEY, GEMINI_MODEL_NAME,
    GEMINI_TIMEOUT_SECONDS, GEMINI_MAX_RETRIES, GEMINI_RETRY_BASE_SECONDS,
)

logger = logging.getLogger(__name__)

# Initialize Gemini Client if API key is present
client = None
_response_cache: Dict[str, str] = {}
_gemini_quota_exhausted = False
def get_client():
    global client
    if DISABLE_GEMINI or _gemini_quota_exhausted:
        return None
    if client is None and GEMINI_API_KEY:
        try:
            client = genai.Client(
                api_key=GEMINI_API_KEY,
                http_options=types.HttpOptions(timeout=int(GEMINI_TIMEOUT_SECONDS * 1000)),
            )
            logger.info(f"Initialized Gemini client with model {GEMINI_MODEL_NAME}")
        except Exception as e:
            logger.warning(f"Failed to initialize Gemini client: {e}")
    return client


def _call_gemini_with_retry(prompt: str, max_retries: int = GEMINI_MAX_RETRIES) -> str:
    global _gemini_quota_exhausted
    cache_key = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    if cache_key in _response_cache:
        return _response_cache[cache_key]

    c = get_client()
    if not c:
        raise RuntimeError("Gemini client not initialized (missing API key)")

    delay = GEMINI_RETRY_BASE_SECONDS

    def generate():
        return c.models.generate_content(
            model=GEMINI_MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )

    for attempt in range(max_retries + 1):
        try:
            executor = ThreadPoolExecutor(max_workers=1)
            future = executor.submit(generate)
            try:
                response = future.result(timeout=GEMINI_TIMEOUT_SECONDS)
            finally:
                executor.shutdown(wait=False, cancel_futures=True)
            result = response.text.strip()
            _response_cache[cache_key] = result
            return result
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "rate" in err_str.lower():
                # Daily/project quota errors will not recover by retrying. Do
                # not block the whole document behind repeated sleeps.
                if "quota" in err_str.lower() or "exceeded" in err_str.lower():
                    _gemini_quota_exhausted = True
                    logger.error("Gemini quota exhausted; disabling Gemini for this process and using local extraction.")
                    raise RuntimeError("Gemini quota exhausted") from e
                if attempt < max_retries:
                    logger.warning(f"Gemini API rate limited (attempt {attempt+1}/{max_retries + 1}). Retrying in {delay}s...")
                    time.sleep(delay)
                    delay = min(5.0, delay * 1.5)
            else:
                if isinstance(e, FuturesTimeoutError):
                    logger.warning("Gemini request timed out after %.1fs", GEMINI_TIMEOUT_SECONDS)
                if attempt >= max_retries:
                    raise RuntimeError("Gemini request failed within bounded retry budget") from e
                time.sleep(delay)
                delay = min(5.0, delay * 1.5)
    raise RuntimeError("Gemini request failed")


def validate_fact_record(fact: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Validate grounding and required fields without inventing evidence."""
    quote = str(fact.get("source_quote") or "")
    attrs = fact.get("attributes")
    start, end = fact.get("char_start"), fact.get("char_end")
    if not quote or not isinstance(attrs, dict):
        return None
    required = ("entity", "metric", "value", "unit", "period", "scope")
    attrs = {key: attrs.get(key, "") for key in required} | {
        key: value for key, value in attrs.items() if key not in required
    }
    normalized = f"{attrs.get('entity', '')} | {attrs.get('metric', '')} | {attrs.get('period', '')}".lower()
    result = {**fact, "attributes": attrs, "normalized_signature": fact.get("normalized_signature") or normalized}
    if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end < start:
        return None
    result["status"] = "uncertain" if result.get("status") not in {"normal", "uncertain"} else result["status"]
    missing = [key for key in required if not str(attrs.get(key) or "").strip()]
    if missing and result["status"] == "normal":
        result["status"] = "uncertain"
        result["uncertainty_reason"] = (
            result.get("uncertainty_reason")
            or f"Evidence is missing required field(s): {', '.join(missing)}."
        )
    raw_value = str(attrs.get("value") or "").replace(",", "")
    number_match = re.search(r"-?\d+(?:\.\d+)?", raw_value)
    if number_match:
        number = float(number_match.group(0))
        unit = str(attrs.get("unit") or "").lower()
        if "%" in raw_value or "%" in unit or "percent" in unit:
            if number < -100 or number > 200:
                return None
        if re.search(rf"\b(?:page|p\.?)\s*{re.escape(number_match.group(0))}\b", quote, re.IGNORECASE):
            return None
    return result


def validate_fact_records(facts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [checked for fact in facts if (checked := validate_fact_record(fact))]


def _annotate_table_uncertainty(facts: List[Dict[str, Any]], statement_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    if statement_data.get("table_status") != "malformed":
        return facts
    for fact in facts:
        fact["status"] = "uncertain"
        fact["uncertainty_reason"] = "Malformed table layout prevented reliable row/column association."
    return facts


def extract_facts_from_statement(
    statement_data: Dict[str, Any],
    document_filename: str
) -> List[Dict[str, Any]]:
    """
    Extracts grounded factual claims from a single candidate statement.
    Uses Gemini API if available, otherwise falls back to structural heuristic extraction.
    """
    statement_text = statement_data["statement"]
    page_number = statement_data["page_number"]
    char_start = statement_data["char_start"]
    char_end = statement_data["char_end"]

    if statement_data.get("position_valid") is False:
        return []
    if statement_data.get("table_status") == "malformed":
        return [{
            "page_number": page_number,
            "source_quote": statement_text,
            "char_start": char_start,
            "char_end": char_end,
            "attributes": {
                "entity": _document_entity(document_filename),
                "metric": "",
                "value": "",
                "unit": "",
                "period": "",
                "scope": "",
            },
            "normalized_signature": "",
            "status": "uncertain",
            "uncertainty_reason": "table structure could not be reliably parsed",
        }]

    # Headers, prose and page furniture do not need an LLM call. Keep this
    # gate deliberately broad so metric synonyms and ambiguous claims remain
    # eligible for extraction.
    fact_signal = re.search(
        r"\b(revenue|sales|margin|income|profit|headcount|employees?|growth|cost|ebitda|cash|assets?|liabilit(?:y|ies))\b"
        r"|(?:\$|%|\b\d[\d,.]*(?:\s*(?:million|billion|thousand|m|bn|k))?\b)",
        statement_text,
        re.IGNORECASE,
    )
    if not statement_data.get("position_valid", True):
        return []
    if not fact_signal:
        return []

    structured = _extract_structured_local_facts(
        statement_text, page_number, char_start, char_end, document_filename
    )
    if structured:
        return validate_fact_records(_annotate_table_uncertainty(structured, statement_data))

    if get_client():
        try:
            return validate_fact_records(_annotate_table_uncertainty(_extract_with_gemini(
                statement_text, page_number, char_start, char_end, document_filename
            ), statement_data))
        except Exception as e:
            logger.error(f"Gemini API extraction error: {e}. Falling back to rule extractor.")

    # Rule-based fallback extractor
    return validate_fact_records(_annotate_table_uncertainty(_extract_with_rules(
        statement_text, page_number, char_start, char_end, document_filename
    ), statement_data))


def _document_entity(filename: str) -> str:
    base = filename.rsplit(".", 1)[0]
    base = re.sub(r"^[\d\-_]+", "", base).replace("-", " ").replace("_", " ")
    base = re.sub(r"\b(?:q[1-4]\s*fy\s*\d{2,4}|q[1-4]|fy\s*\d{2,4})\b", "", base, flags=re.IGNORECASE)
    base = re.sub(r"\b(?:report|presentation|update|analysis|prospectus|annual|earnings)\b", "", base, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", base).strip().title() or "Unknown Entity"


def _latest_period(text: str) -> str:
    half = re.search(
        r"\b(first|second)\s+half\s+of\s+(?:fiscal\s+)?(?:year\s+)?(20\d{2}|\d{2})\b",
        text, re.IGNORECASE,
    )
    if half:
        year = half.group(2)
        year = f"20{year}" if len(year) == 2 else year
        return f"H{'1' if half.group(1).lower() == 'first' else '2'} FY{year[-2:]}"
    ended = re.search(
        r"\b(?:three|six|nine|twelve|\d+)\s+months?\s+(?:period\s+)?ended\s+"
        r"(?:[A-Za-z]+\s+\d{1,2},?\s+)?(20\d{2})\b",
        text, re.IGNORECASE,
    )
    if ended:
        months = re.search(r"\b(three|six|nine|twelve|\d+)\s+months?", ended.group(0), re.IGNORECASE).group(1)
        return f"{months} months ended {ended.group(1)}"
    matches = []
    for q, q_year, fy_year in re.findall(
        r"\b(q[1-4])\s*fy\s*(\d{2,4})\b|\b(?:fy|fiscal year)\s*(\d{2,4})\b",
        text, re.IGNORECASE,
    ):
        year = q_year or fy_year
        year = f"20{year}" if len(year) == 2 else year
        matches.append((int(year), f"{q.upper()} FY{year[-2:]}" if q else f"FY {year}"))
    if not matches:
        years = re.findall(r"\b20\d{2}\b", text)
        return f"FY {years[-1]}" if years else "unspecified period"
    return sorted(matches)[-1][1]


def _local_fact(text, page_number, char_start, char_end, entity, metric, value, unit, period):
    quote = text.strip()
    return {
        "page_number": page_number,
        "source_quote": quote,
        "char_start": char_start,
        "char_end": char_end,
        "attributes": {
            "entity": entity,
            "metric": metric,
            "value": value,
            "unit": unit,
            "period": period,
            "scope": "consolidated",
        },
        "normalized_signature": f"{entity.lower()} | {metric.lower()} | {period.lower()}",
        "status": "normal",
        "uncertainty_reason": None,
    }


def _extract_structured_local_facts(text, page_number, char_start, char_end, filename):
    """Extract reliable latest-period values from common PDF table rows.

    PyMuPDF exposes chart/table cells as separate lines. This handles the
    presentation's row labels and latest-period values without mistaking page
    numbers, fiscal years, or chart percentages for financial facts.
    """
    compact = " ".join(line.strip() for line in text.splitlines() if line.strip())
    entity = _document_entity(filename)
    period = _latest_period(compact)
    facts = []

    row_patterns = [
        (r"team size(?:\s*\([^)]*\))?", "employee headcount", "count"),
        (r"active customers", "active customers", "count"),
        (r"revenue from services", "revenue", "INR crore"),
        (r"total revenue from customers", "revenue", "INR crore"),
        (r"service ebitda margin", "EBITDA margin", "%"),
        (r"ebitda margin", "EBITDA margin", "%"),
        (r"adjusted ebitda", "EBITDA", "INR crore"),
        (r"reported ebitda", "EBITDA", "INR crore"),
        (r"net working capital \(days\)", "net working capital days", "days"),
    ]

    for label_pattern, metric, unit in row_patterns:
        label_matches = list(re.finditer(label_pattern, compact, re.IGNORECASE))
        if not label_matches:
            continue
        # Prefer the occurrence attached to a period header (e.g. FY24
        # revenue from services) over explanatory footnotes.
        match = max(
            label_matches,
            key=lambda item: int(bool(re.search(
                r"\b(?:q[1-4]\s*)?fy\s*\d{2,4}\b",
                compact[max(0, item.start() - 35):item.start()], re.IGNORECASE
            )))
        )
        before = compact[max(0, match.start() - 220):match.start()]
        after = compact[match.end():match.end() + 260]
        local_window = before + " " + after
        number_re = re.compile(r"(?<![A-Za-z])\(?-?\d[\d,]*(?:\.\d+)?\)?")
        before_values = [m.group(0) for m in number_re.finditer(before)
                         if not 1900 <= float(m.group(0).replace(",", "").replace("(", "").replace(")", "")) <= 2100]
        after_values = [m.group(0) for m in number_re.finditer(after)
                        if not 1900 <= float(m.group(0).replace(",", "").replace("(", "").replace(")", "")) <= 2100]
        if unit == "INR crore":
            money_matches = list(re.finditer(
                r"(?:₹|rs\.?)[\s]*\(?-?[\d,]+(?:\.\d+)?\)?\s*(?:cr|crore|million|mn)?",
                compact, re.IGNORECASE,
            ))
            money_matches = sorted(money_matches, key=lambda item: abs(item.start() - match.start()))
            candidates = [re.search(r"-?[\d,]+(?:\.\d+)?", item.group(0)).group(0)
                          for item in money_matches[:4]
                          if abs(item.start() - match.start()) <= 300]
        elif unit == "%":
            percent_matches = list(re.finditer(r"\(?-?[\d,]+(?:\.\d+)?\)?\s*%", compact))
            percent_matches = sorted(percent_matches, key=lambda item: abs(item.start() - match.start()))
            candidates = [item.group(0) for item in percent_matches[:4]
                          if abs(item.start() - match.start()) <= 300]
        else:
            candidates = after_values[:4] if len(after_values) >= 1 else before_values[-4:]
        if not candidates:
            candidates = after_values[:4] if len(after_values) >= 1 else before_values[-4:]
        if not candidates:
            continue
        # Dashboard labels can be separated from the value by unrelated
        # cells/footnotes. For active customers, require a value immediately
        # attached to the label; otherwise a page artifact can become -24.
        if metric == "active customers":
            direct_value = re.match(r"\s*(?:>|\()?\s*\d[\d,]*(?:\.\d+)?", after)
            if not direct_value:
                continue
        selected = candidates[0] if unit in {"INR crore", "%"} else candidates[-1]
        value = selected.replace("(", "-").replace(")", "")
        facts.append(_local_fact(text, page_number, char_start, char_end, entity, metric, value, unit, period))

    # Narrative highlight: "EBITDA increased ... to Rs. 127 Cr ... FY23".
    ebitda_match = re.search(r"ebitda[^.]{0,100}?to\s+rs\.?\s*([\d,.]+)\s*cr", compact, re.IGNORECASE)
    if ebitda_match and not any(f["attributes"]["metric"] == "EBITDA" for f in facts):
        facts.append(_local_fact(text, page_number, char_start, char_end, entity, "EBITDA",
                                 ebitda_match.group(1), "INR crore", period))

    # Deduplicate overlapping row matches.
    unique = {}
    for fact in facts:
        key = (fact["attributes"]["metric"], fact["attributes"]["value"], fact["attributes"]["period"])
        unique[key] = fact
    return list(unique.values())


def extract_facts_from_statements(
    statements: List[Dict[str, Any]], document_filename: str, batch_size: int = 8
) -> List[Dict[str, Any]]:
    """Extract facts from several statements in one request.

    Batching keeps prompts small enough for reliable JSON output while removing
    one network round trip per sentence.
    """
    results: List[Dict[str, Any]] = []
    for start in range(0, len(statements), batch_size):
        batch = statements[start:start + batch_size]
        eligible = [
            (index, item) for index, item in enumerate(batch)
            if re.search(
                r"\b(revenue|sales|margin|income|profit|headcount|employees?|growth|cost|ebitda|cash|assets?|liabilit(?:y|ies))\b"
                r"|(?:\$|%|\b\d[\d,.]*(?:\s*(?:million|billion|thousand|m|bn|k))?\b)",
                item["statement"], re.IGNORECASE
            ) and item.get("position_valid", True) and item.get("table_status") != "malformed"
        ]
        if not eligible or not get_client():
            for _, item in enumerate(batch):
                results.extend(extract_facts_from_statement(item, document_filename))
            continue

        payload = "\n".join(
            f"STATEMENT {index}: {item['statement']}" for index, item in eligible
        )
        prompt = f"""
Extract all distinct factual claims from the following statements in document '{document_filename}'.
Return one JSON object per statement, preserving its index:
[{{"statement_index": 0, "facts": [{{
  "source_quote": "exact substring", "status": "normal" or "uncertain",
  "uncertainty_reason": null or "explanation",
  "attributes": {{"entity": "", "metric": "", "value": "", "unit": "", "period": "", "scope": ""}},
  "normalized_signature": "entity | metric | period"
}}]}}]
Use [] when a statement contains no factual claim. JSON only.

{payload}
"""
        try:
            for index, item in enumerate(batch):
                if not any(index == eligible_index for eligible_index, _ in eligible):
                    results.extend(extract_facts_from_statement(item, document_filename))
            parsed = json.loads(_call_gemini_with_retry(prompt))
            by_index = {
                int(item.get("statement_index")): item.get("facts", [])
                for item in parsed if isinstance(item, dict)
            }
            for index, statement in enumerate(batch):
                facts_for_statement = by_index.get(index)
                if facts_for_statement is None:
                    # A malformed or partial model response must not silently
                    # delete a statement from the extraction result.
                    results.extend(_extract_with_rules(
                        statement["statement"], statement["page_number"],
                        statement["char_start"], statement["char_end"], document_filename
                    ))
                    continue
                for fact in facts_for_statement:
                    quote = fact.get("source_quote", statement["statement"])
                    if quote not in statement["statement"]:
                        quote = statement["statement"]
                    quote_start = statement["char_start"] + statement["statement"].find(quote)
                    results.append({
                        "page_number": statement["page_number"],
                        "source_quote": quote,
                        "char_start": quote_start,
                        "char_end": quote_start + len(quote),
                        "attributes": fact.get("attributes", {}),
                        "normalized_signature": fact.get("normalized_signature", ""),
                        "status": fact.get("status", "normal"),
                        "uncertainty_reason": fact.get("uncertainty_reason"),
                    })
        except Exception as exc:
            logger.error(f"Gemini batch extraction error: {exc}. Falling back to rules.")
            for _, item in eligible:
                results.extend(_extract_with_rules(
                    item["statement"], item["page_number"], item["char_start"],
                    item["char_end"], document_filename
                ))
    return validate_fact_records(results)


def verify_extracted_facts(facts: List[Dict[str, Any]], document_filename: str,
                          batch_size: int = 24) -> List[Dict[str, Any]]:
    """Verify parser output with Gemini without inventing new facts."""
    if not facts or not get_client():
        return facts

    verified: List[Dict[str, Any]] = []
    for start in range(0, len(facts), batch_size):
        batch = facts[start:start + batch_size]
        payload = [{
            "index": index,
            "source_quote": fact.get("source_quote", ""),
            "attributes": fact.get("attributes", {}),
        } for index, fact in enumerate(batch)]
        prompt = f"""
Verify facts extracted by a PDF parser from '{document_filename}'. Use only
source_quote as evidence. Do not add facts, delete facts, or change quotes.
Correct attributes only when explicitly supported. Mark uncertain when a value
is a layout artifact, a table heading lacks a row/total, or the metric/period
is ambiguous. Distinguish events such as promotions or shipments from stock
measures such as headcount.

Return JSON only: [{{"index": 0, "status": "normal"|"uncertain",
"uncertainty_reason": null|string, "attributes": {{"entity": "",
"metric": "", "value": "", "unit": "", "period": "", "scope": ""}}}}]

Parser output:
{json.dumps(payload, ensure_ascii=False)}
"""
        try:
            parsed = json.loads(_call_gemini_with_retry(prompt))
            by_index = {
                int(item["index"]): item for item in parsed
                if isinstance(item, dict) and "index" in item
            }
            for index, original in enumerate(batch):
                checked = by_index.get(index)
                if not checked or not isinstance(checked.get("attributes"), dict):
                    verified.append(original)
                    continue
                corrected = dict(original)
                attrs = {
                    **(original.get("attributes") or {}),
                    **{
                        key: value for key, value in checked["attributes"].items()
                        if value not in (None, "")
                    },
                }
                corrected["attributes"] = attrs
                corrected["status"] = checked.get("status", original.get("status", "normal"))
                corrected["uncertainty_reason"] = checked.get(
                    "uncertainty_reason", original.get("uncertainty_reason")
                )
                corrected["normalized_signature"] = (
                    f"{attrs.get('entity', '')} | {attrs.get('metric', '')} | {attrs.get('period', '')}"
                ).lower()
                verified.append(corrected)
        except Exception as exc:
            logger.warning("Gemini fact verification failed; retaining parser output: %s", exc)
            verified.extend(batch)
    return validate_fact_records(verified)


def _extract_with_gemini(
    text: str, page_number: int, char_start: int, char_end: int, document_filename: str
) -> List[Dict[str, Any]]:
    prompt = f"""
    Analyze the following sentence from document '{document_filename}' (Page {page_number}):
    "{text}"

    Task:
    Extract all distinct factual claims.
    For each factual claim:
    1. Extract flexible attributes: entity, metric, value, unit, period, scope, qualifier (only include fields supported by text).
    2. Create a normalized_signature string (e.g. "entity | metric | period").
    3. Verbatim source_quote must match exact original substring.
    4. If the statement is ambiguous, vague, or missing referents (e.g. "Growth was 24%" without specifying entity or metric), set status to "uncertain" and provide an explicit "uncertainty_reason".

    Return JSON array of facts matching this schema:
    [
      {{
        "source_quote": "{text}",
        "status": "normal" or "uncertain",
        "uncertainty_reason": null or "explanation...",
        "attributes": {{
          "entity": "...",
          "metric": "...",
          "value": "...",
          "unit": "...",
          "period": "...",
          "scope": "..."
        }},
        "normalized_signature": "..."
      }}
    ]

    If no factual claim is present, return []. Respond with valid JSON array only.
    """

    result_text = _call_gemini_with_retry(prompt)
    data = json.loads(result_text)
    
    facts = []
    for item in data:
        quote = item.get("source_quote", text)
        if quote not in text:
            quote = text
        quote_start = char_start + text.find(quote)
        facts.append({
            "page_number": page_number,
            "source_quote": quote,
            "char_start": quote_start,
            "char_end": quote_start + len(quote),
            "attributes": item.get("attributes", {}),
            "normalized_signature": item.get("normalized_signature", ""),
            "status": item.get("status", "normal"),
            "uncertainty_reason": item.get("uncertainty_reason")
        })

    return facts


def _extract_with_rules(
    text: str, page_number: int, char_start: int, char_end: int, document_filename: str
) -> List[Dict[str, Any]]:
    """
    Deterministic rule-based factual extractor for offline/demo reliability.
    """
    # Generic ambiguity handling: a quantified growth claim without a metric
    # or referent must remain uncertain, regardless of the wording used.
    lower_text = text.lower()
    metric_terms = ("revenue", "sales", "margin", "income", "profit", "headcount", "employees", "cost", "ebitda", "market share")
    if re.search(r"\b(growth|grew|increased|decreased)\b", lower_text) and "%" in text and not any(term in lower_text for term in metric_terms):
        percent = re.search(r"-?[\d,.]+\s*%", text)
        value = percent.group(0) if percent else "unspecified"
        return [{
            "page_number": page_number,
            "source_quote": text,
            "char_start": char_start,
            "char_end": char_end,
            "attributes": {
                "metric": "growth",
                "value": value,
                "unit": "%",
                "qualifier": "referent not specified"
            },
            "normalized_signature": "unspecified entity | growth | ambiguous period",
            "status": "uncertain",
            "uncertainty_reason": "The quantified growth claim does not identify the metric, entity, or reporting period."
        }]

    # Regex patterns for entities, numbers, currency, percentages, periods
    # Derive entity from document filename — strip extension and numeric prefix, take first meaningful part
    base = document_filename.rsplit('.', 1)[0]  # remove .pdf
    # Remove leading numeric/date tokens (e.g. "01-" or "2024-")
    import re as _re
    base = _re.sub(r'^[\d\-_]+', '', base).strip('-_ ')
    entity = base.replace('-', ' ').replace('_', ' ').title() if base else "Unknown Entity"
    # Cap to first 3 words to keep signatures concise
    entity = ' '.join(entity.split()[:3]) if entity else "Unknown Entity"

    
    metric = None
    # Prefer the claim's subject over incidental words in supporting context.
    # For example, "market share ... in terms of revenue" is market share,
    # not revenue.
    if re.search(r"\bpromot(?:ed|ions?)\b.{0,80}\b(?:team members?|employees?)\b", text, re.IGNORECASE | re.DOTALL):
        metric = "employee promotions"
    elif re.search(r"%\s+of\s+(?:our\s+)?revenues?\s+were\s+from\s+customers", text, re.IGNORECASE):
        metric = "revenue composition"
    elif re.search(r"\bmarket\s+share\b", text, re.IGNORECASE):
        metric = "market share"
    elif "revenue" in text.lower():
        metric = "revenue"
    elif "operating margin" in text.lower() or "margin" in text.lower():
        metric = "operating margin"
    elif "employee headcount" in text.lower() or "headcount" in text.lower() or "employed" in text.lower() or "team members" in text.lower():
        metric = "employee headcount"
    elif "net income" in text.lower():
        metric = "net income"

    if not metric:
        # Skip sentences without clear metric
        return []

    # Extract values while excluding years and page numbers. A table containing
    # several values is retained as uncertain instead of creating a false hard
    # relationship from whichever number happens to appear first.
    number_pattern = re.compile(
        r"(?:₹|\$|rs\.?\s*)?\s*-?\d[\d,]*(?:\.\d+)?\s*(?:%|million|billion|thousand|mn|bn|cr|m|k)?",
        re.IGNORECASE,
    )
    value_candidates = []
    for match in number_pattern.finditer(text):
        raw = match.group(0).strip().rstrip(".,")
        numeric = re.search(r"-?\d[\d,]*(?:\.\d+)?", raw)
        if not numeric:
            continue
        number = float(numeric.group(0).replace(",", ""))
        if 1900 <= number <= 2100:
            continue
        prefix = text[max(0, match.start() - 12):match.start()].lower()
        if "fiscal" in prefix or "year" in prefix:
            continue
        value_candidates.append(raw)
    val_str = value_candidates[0] if value_candidates else "unspecified"
    if "$" in val_str or "₹" in val_str or "₹" in text or re.search(r"\brs\.?\b|\busd\b", text, re.IGNORECASE):
        unit = "INR" if ("₹" in text or re.search(r"\brs\.?\b", text, re.IGNORECASE)) else "USD"
    elif "%" in val_str:
        unit = "%"
    elif re.search(r"\b(?:million|billion|thousand|mn|bn|cr)\b", val_str, re.IGNORECASE) and metric in {"revenue", "operating margin", "net income"}:
        unit = "currency"
    else:
        unit = "count" if val_str != "unspecified" else "units"

    # The fallback parser cannot reliably assign one value from a table-sized
    # block. Dropping these blocks is safer than manufacturing relationships
    # from the first page number or table cell.
    if len(value_candidates) > 1 or val_str == "unspecified":
        return []

    # Extract the period from the evidence instead of assuming FY 2023.
    period_matches = re.findall(
        r"\b(q[1-4])\s*(?:fy\s*)?(20\d{2}|\d{2})\b|\b(fy|fiscal year)\s*(20\d{2}|\d{2})\b|\bfiscal\s+(20\d{2})\b",
        text, re.IGNORECASE,
    )
    periods = []
    for quarter, q_year, fy_label, fy_year, fiscal_year in period_matches:
        year = q_year or fy_year or fiscal_year
        year = f"20{year}" if len(year) == 2 else year
        periods.append(f"{quarter.upper()} {year}" if quarter else f"FY {year}")
    periods = list(dict.fromkeys(periods))
    if len(periods) > 1:
        return []
    period = periods[0] if periods else "unspecified period"
    status = "normal"
    uncertainty_reason = None

    attributes = {
        "entity": entity,
        "metric": metric,
        "value": val_str,
        "unit": unit,
        "period": period,
        "scope": "global"
    }

    norm_sig = f"{entity.lower()} | {metric.lower()} | {period.lower()}"

    return [{
        "page_number": page_number,
        "source_quote": text,
        "char_start": char_start,
        "char_end": char_end,
        "attributes": attributes,
        "normalized_signature": norm_sig,
        "status": status,
        "uncertainty_reason": uncertainty_reason
    }]


def classify_fact_relationship(
    fact_a: Dict[str, Any],
    fact_b: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Classifies relationship between Fact A and Fact B into:
    corroborated, contradicted, reconciled, or uncertain.
    Includes structured JSON reasoning trace.
    """
    # Prefer the deterministic classifier. Gemini is reserved for pairs whose
    # normalized fields are genuinely insufficient to decide the relationship.
    rule_result = _classify_with_rules(fact_a, fact_b)
    if rule_result["relationship_type"] != "uncertain":
        return _with_evidence_checklist(rule_result, fact_a, fact_b)
    # Unit/scope mismatches are deterministic comparability decisions. Do not
    # send them to Gemini, both to avoid latency and to prevent a model from
    # turning a percentage-vs-count pair into a false contradiction.
    rule_reasoning = rule_result.get("reasoning") or {}
    if rule_reasoning.get("reconciliation_dimension") in {"Unit", "Scope"}:
        return _with_evidence_checklist(rule_result, fact_a, fact_b)
    if fact_a.get("status") == "uncertain" or fact_b.get("status") == "uncertain":
        return _with_evidence_checklist(rule_result, fact_a, fact_b)

    if get_client():
        try:
            return _with_evidence_checklist(_classify_with_gemini(fact_a, fact_b), fact_a, fact_b)
        except Exception as e:
            logger.error(f"Gemini relationship classification error: {e}. Falling back to rules.")

    return _with_evidence_checklist(rule_result, fact_a, fact_b)


def _with_evidence_checklist(
    result: Dict[str, Any], fact_a: Dict[str, Any], fact_b: Dict[str, Any]
) -> Dict[str, Any]:
    """Attach the six comparable dimensions to every classification."""
    attrs_a, attrs_b = fact_a.get("attributes") or {}, fact_b.get("attributes") or {}
    entity_a, entity_b = _norm_entity(attrs_a.get("entity")), _norm_entity(attrs_b.get("entity"))
    metric_a, metric_b = _norm_metric(attrs_a.get("metric")), _norm_metric(attrs_b.get("metric"))
    period_a, period_b = _norm_period(attrs_a.get("period")), _norm_period(attrs_b.get("period"))
    _, unit_a = _normalized_number(attrs_a.get("value"), attrs_a.get("unit"))
    _, unit_b = _normalized_number(attrs_b.get("value"), attrs_b.get("unit"))
    qualifier_a = _norm_text(attrs_a.get("qualifier") or attrs_a.get("context"))
    qualifier_b = _norm_text(attrs_b.get("qualifier") or attrs_b.get("context"))
    checklist = {
        "entity": bool(entity_a and entity_b and (entity_a == entity_b or entity_a in entity_b or entity_b in entity_a)),
        "metric": bool(metric_a and metric_b and metric_a == metric_b),
        "period": bool(period_a and period_b and period_a == period_b),
        "unit": bool(unit_a and unit_b and unit_a == unit_b),
        "scope": bool(_norm_text(attrs_a.get("scope")) and _norm_text(attrs_a.get("scope")) == _norm_text(attrs_b.get("scope"))),
        "qualifier": bool(qualifier_a == qualifier_b),
    }
    score = round(0.25 + sum(checklist.values()) * 0.12, 2)
    reasoning = dict(result.get("reasoning") or {})
    reasoning["checklist"] = checklist
    reasoning["same_qualifier"] = checklist["qualifier"]
    reasoning["evidence_confidence"] = score
    result["reasoning"] = reasoning
    result["confidence"] = round(min(0.99, max(0.0, min(float(result.get("confidence", score)), score + 0.15))), 2)
    return result


def _classify_with_gemini(fact_a: Dict[str, Any], fact_b: Dict[str, Any]) -> Dict[str, Any]:
    prompt = f"""
    Compare the following two extracted facts from documents:

    Fact A:
    Quote: "{fact_a.get('source_quote')}"
    Attributes: {json.dumps(fact_a.get('attributes', {}))}
    Status: {fact_a.get('status')}

    Fact B:
    Quote: "{fact_b.get('source_quote')}"
    Attributes: {json.dumps(fact_b.get('attributes', {}))}
    Status: {fact_b.get('status')}

    Task:
    Determine relationship:
    - "corroborated": Both facts assert the exact same core metric & value for the same entity and time period, even if phrased differently or expressed in equivalent units.
    - "contradicted": Both facts refer to the exact same entity, metric, time period, unit, and scope, but assert genuinely conflicting values.
    - "reconciled": Facts appear conflicting at first glance, but are contextually reconciled by a specific dimension (e.g., different time periods like Q3 vs Full Year, different units, different scope).
    - "uncertain": At least one fact is ambiguous or relationship cannot be determined with confidence.

    Return JSON matching this schema:
    {{
      "relationship_type": "corroborated" | "contradicted" | "reconciled" | "uncertain",
      "confidence": float 0.0 to 1.0,
      "reasoning": {{
        "same_entity": bool,
        "same_metric": bool,
        "same_period": bool,
        "same_unit": bool,
        "same_scope": bool,
        "reconciliation_dimension": null or "Time Period" or "Unit" or "Scope",
        "reasoning_steps": [
          "Step 1: ...",
          "Step 2: ...",
          "Conclusion: ..."
        ],
        "summary": "Short clear natural language explanation..."
      }}
    }}
    Respond with JSON only.
    """

    result_text = _call_gemini_with_retry(prompt)
    return json.loads(result_text)


def _norm_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _norm_entity(value: Any) -> str:
    """Reduce filename-derived names to the underlying company/entity."""
    text = _norm_text(value)
    # These words describe the source document, not the entity being measured.
    text = re.sub(
        r"\b(prospectus|annual|quarterly|earnings|presentation|report|update|analysis|market|excerpt)\b",
        " ", text,
    )
    text = re.sub(r"\b(?:q[1-4]|fy)\s*\d{2,4}\b", " ", text)
    text = re.sub(r"\b20\d{2}\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _norm_period(value: Any) -> str:
    text = _norm_text(value)
    replacements = {
        "third quarter": "q3",
        "fourth quarter": "q4",
        "first quarter": "q1",
        "second quarter": "q2",
        "full year": "fy",
        "fiscal year": "fy",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _norm_metric(value: Any) -> str:
    text = _norm_text(value)
    if "market share" in text or "share of market" in text:
        return "market share"
    if "revenue composition" in text or "revenue share" in text:
        return "revenue composition"
    if "revenue" in text or "sales" in text:
        return "revenue"
    if "ebitda" in text and "margin" in text:
        return "ebitda margin"
    if "operating" in text and "margin" in text:
        return "operating margin"
    if "margin" in text:
        return "margin"
    text = text.replace("employees", "headcount").replace("team members", "headcount")
    text = text.replace("operating profit margin", "operating margin")
    return text


def _normalized_number(value: Any, unit: Any) -> tuple[Optional[float], str]:
    raw = str(value or "").lower().replace(",", "").replace(" ", "")
    match = re.search(r"[-+]?\d*\.?\d+", raw)
    if not match:
        return None, _norm_text(unit)
    number = float(match.group(0))
    suffix = raw[match.end():]
    if "billion" in raw or suffix.startswith("bn") or suffix.startswith("b"):
        number *= 1_000_000_000
    elif "million" in raw or suffix.startswith("m"):
        number *= 1_000_000
    elif "thousand" in raw or suffix.startswith("k"):
        number *= 1_000
    normalized_unit = _norm_text(unit)
    if "%" in raw or normalized_unit in {"percent", "%", "pct"}:
        normalized_unit = "percent"
    elif "$" in raw or normalized_unit in {"usd", "dollar", "dollars"}:
        normalized_unit = "usd"
    return number, normalized_unit


def _extraction_quality_issue(fact: Dict[str, Any]) -> Optional[str]:
    """Identify fallback-parser output that should not form a hard edge."""
    attrs = fact.get("attributes") or {}
    metric = _norm_metric(attrs.get("metric"))
    value = str(attrs.get("value") or "").strip().lower()
    raw_unit = str(attrs.get("unit") or "").lower()
    unit = "percent" if "%" in raw_unit or "percent" in raw_unit or "pct" in raw_unit else _norm_text(raw_unit)
    period = _norm_period(attrs.get("period"))
    if metric in {"revenue", "margin", "operating margin", "ebitda margin", "net income"} and unit in {"count", "units", ""}:
        return f"{metric} has no reliable currency/percentage unit ({attrs.get('unit')!r})"
    if value in {"", "unspecified", ","}:
        return f"{metric} has no numeric value"
    quote = str(fact.get("source_quote") or "")
    normalized_value = re.sub(r"[^0-9.-]", "", value)
    if normalized_value and re.search(
        rf"\bpage\s+{re.escape(normalized_value)}\b", quote, re.IGNORECASE
    ):
        return f"value {attrs.get('value')!r} is a page reference, not a metric value"
    if re.search(r"breakdown of .*employees?.*by function", quote, re.IGNORECASE | re.DOTALL):
        return "employee breakdown table excerpt does not identify a total or row label"
    trend_percentages = re.findall(r"\(?-?\d[\d,.]*\)?\s*%", quote)
    if len(trend_percentages) > 1 and re.search(
        r"\b(?:improved|declined|declining|increased|decreased)\b", quote, re.IGNORECASE
    ):
        return "multi-period trend contains multiple values that require period-level alignment"
    quote_years = set(re.findall(r"\b(?:19|20)\d{2}\b", str(fact.get("source_quote") or "")))
    period_years = set(re.findall(r"\b(?:19|20)\d{2}\b", period))
    if quote_years and period_years and not quote_years.intersection(period_years):
        return f"source mentions years {sorted(quote_years)} but extracted period is {attrs.get('period')!r}"
    return None


def _rule_confidence(*, same_entity: bool, same_metric: bool, same_period: bool,
                     same_unit: bool, same_scope: bool, numeric_evidence: bool,
                     base: float = 0.45) -> float:
    """Score evidence dimensions instead of assigning confidence by label."""
    score = base
    score += 0.10 if same_entity else 0.0
    score += 0.10 if same_metric else 0.0
    score += 0.10 if same_period else 0.0
    score += 0.10 if same_unit else 0.0
    score += 0.05 if same_scope else 0.0
    score += 0.10 if numeric_evidence else 0.0
    return round(min(0.99, score), 2)


def _classify_with_rules(fact_a: Dict[str, Any], fact_b: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic rule classifier for relationship edges.
    """
    st_a = fact_a.get("status")
    st_b = fact_b.get("status")

    if st_a == "uncertain" or st_b == "uncertain":
        confidence = _rule_confidence(
            same_entity=False, same_metric=False, same_period=False,
            same_unit=False, same_scope=False, numeric_evidence=False, base=0.30,
        )
        return {
            "relationship_type": "uncertain",
            "confidence": confidence,
            "reasoning": {
                "same_entity": False,
                "same_metric": False,
                "same_period": False,
                "same_unit": False,
                "same_scope": False,
                "reconciliation_dimension": None,
                "reasoning_steps": [
                    "Step 1: Inspected Fact A and Fact B for extraction certainty.",
                    f"Step 2: Fact status detected: Fact A ({st_a}), Fact B ({st_b}).",
                    "Step 3: Extraction ambiguity prevents confident relationship classification."
                ],
                "summary": "Marked as uncertain because one or both facts contain ambiguous referents in source text."
            }
        }

    quality_a = _extraction_quality_issue(fact_a)
    quality_b = _extraction_quality_issue(fact_b)
    if quality_a or quality_b:
        issues = "; ".join(x for x in [quality_a, quality_b] if x)
        confidence = _rule_confidence(
            same_entity=False, same_metric=False, same_period=False,
            same_unit=False, same_scope=False, numeric_evidence=False, base=0.30,
        )
        return {
            "relationship_type": "uncertain",
            "confidence": confidence,
            "reasoning": {
                "same_entity": False,
                "same_metric": False,
                "same_period": False,
                "same_unit": False,
                "same_scope": False,
                "reconciliation_dimension": None,
                "reasoning_steps": [
                    "Step 1: Inspected extracted attributes for comparability.",
                    f"Step 2: {issues}.",
                    "Conclusion: The edge was not classified because the extracted evidence is unreliable."
                ],
                "summary": f"Relationship is uncertain: {issues}."
            }
        }

    attr_a = fact_a.get("attributes", {})
    attr_b = fact_b.get("attributes", {})

    entity_a, entity_b = _norm_entity(attr_a.get("entity")), _norm_entity(attr_b.get("entity"))
    metric_a, metric_b = _norm_metric(attr_a.get("metric")), _norm_metric(attr_b.get("metric"))
    period_a, period_b = _norm_period(attr_a.get("period")), _norm_period(attr_b.get("period"))
    val_a, val_b = str(attr_a.get("value", "")).strip(), str(attr_b.get("value", "")).strip()

    same_entity = (
        entity_a == entity_b
        or (entity_a and entity_b and (entity_a in entity_b or entity_b in entity_a))
    )
    same_metric = (
        metric_a == metric_b
        or ("margin" in metric_a and "margin" in metric_b)
        or ("revenue" in metric_a and "revenue" in metric_b
            and "composition" not in metric_a and "composition" not in metric_b)
        or ("headcount" in metric_a and "headcount" in metric_b)
        or ("income" in metric_a and "income" in metric_b)
        or ("profit" in metric_a and "profit" in metric_b)
        or ("growth" in metric_a and "growth" in metric_b)
        or ("cost" in metric_a and "cost" in metric_b)
    )
    same_period = period_a == period_b
    num_a, unit_a = _normalized_number(val_a, attr_a.get("unit"))
    num_b, unit_b = _normalized_number(val_b, attr_b.get("unit"))
    same_unit = unit_a == unit_b or not unit_a or not unit_b
    scope_a, scope_b = _norm_text(attr_a.get("scope")), _norm_text(attr_b.get("scope"))
    same_scope = scope_a == scope_b or not scope_a or not scope_b
    same_value = (
        num_a is not None and num_b is not None and same_unit
        and abs(num_a - num_b) <= max(0.01, abs(num_a) * 0.0001)
    )

    if same_entity and same_metric:
        # A percentage change and an absolute count are not contradictory
        # observations. They cannot be compared without a conversion/base.
        if not same_unit:
            confidence = _rule_confidence(
                same_entity=same_entity, same_metric=same_metric,
                same_period=same_period, same_unit=same_unit,
                same_scope=same_scope, numeric_evidence=num_a is not None and num_b is not None,
                base=0.35,
            )
            return {
                "relationship_type": "uncertain",
                "confidence": confidence,
                "reasoning": {
                    "same_entity": same_entity,
                    "same_metric": same_metric,
                    "same_period": same_period,
                    "same_unit": False,
                    "same_scope": same_scope,
                    "reconciliation_dimension": "Unit",
                    "reasoning_steps": [
                        f"Step 1: Entity matched ('{attr_a.get('entity')}' and '{attr_b.get('entity')}').",
                        f"Step 2: Metric matched ('{attr_a.get('metric')}' and '{attr_b.get('metric')}').",
                        f"Step 3: Units differ: '{attr_a.get('unit')}' vs '{attr_b.get('unit')}'.",
                        "Conclusion: The values are not directly comparable without a conversion or denominator."
                    ],
                    "summary": f"Relationship is uncertain because the units differ ({attr_a.get('unit')} vs {attr_b.get('unit')})."
                }
            }
        # Same metric and unit, but different coverage (for example, India
        # operations vs. consolidated group) is contextual, not a conflict.
        if not same_scope:
            confidence = _rule_confidence(
                same_entity=same_entity, same_metric=same_metric,
                same_period=same_period, same_unit=same_unit,
                same_scope=same_scope, numeric_evidence=num_a is not None and num_b is not None,
                base=0.35,
            )
            return {
                "relationship_type": "reconciled",
                "confidence": confidence,
                "reasoning": {
                    "same_entity": same_entity,
                    "same_metric": same_metric,
                    "same_period": same_period,
                    "same_unit": same_unit,
                    "same_scope": False,
                    "reconciliation_dimension": "Scope",
                    "reasoning_steps": [
                        f"Step 1: Entity matched ('{attr_a.get('entity')}' and '{attr_b.get('entity')}').",
                        f"Step 2: Metric matched ('{attr_a.get('metric')}' and '{attr_b.get('metric')}').",
                        f"Step 3: Scope differs: '{attr_a.get('scope')}' vs '{attr_b.get('scope')}'.",
                        "Conclusion: The values are contextualized by scope and are not a direct contradiction."
                    ],
                    "summary": f"Reconciled by Scope: {attr_a.get('scope')} vs {attr_b.get('scope')}."
                }
            }
        if same_period:
            if same_value:
                confidence = _rule_confidence(
                    same_entity=same_entity, same_metric=same_metric,
                    same_period=same_period, same_unit=same_unit,
                    same_scope=same_scope, numeric_evidence=True, base=0.45,
                )
                return {
                    "relationship_type": "corroborated",
                    "confidence": confidence,
                    "reasoning": {
                        "same_entity": True,
                        "same_metric": True,
                        "same_period": True,
                        "same_unit": same_unit,
                        "same_scope": same_scope,
                        "reconciliation_dimension": None,
                        "reasoning_steps": [
                            f"Step 1: Entity matched ('{attr_a.get('entity')}' == '{attr_b.get('entity')}').",
                            f"Step 2: Metric matched ('{attr_a.get('metric')}' == '{attr_b.get('metric')}').",
                            f"Step 3: Time Period matched ('{attr_a.get('period')}' == '{attr_b.get('period')}').",
                            f"Step 4: Values normalized to equivalent numbers ({num_a} == {num_b}).",
                            "Conclusion: Fact B corroborates Fact A across different document phrasings."
                        ],
                        "summary": f"Both documents confirm {attr_a.get('metric')} of {val_a} for {attr_a.get('period')}."
                    }
                }
            else:
                confidence = _rule_confidence(
                    same_entity=same_entity, same_metric=same_metric,
                    same_period=same_period, same_unit=same_unit,
                    same_scope=same_scope, numeric_evidence=num_a is not None and num_b is not None,
                    base=0.45,
                )
                return {
                    "relationship_type": "contradicted",
                    "confidence": confidence,
                    "reasoning": {
                        "same_entity": True,
                        "same_metric": True,
                        "same_period": True,
                        "same_unit": same_unit,
                        "same_scope": same_scope,
                        "reconciliation_dimension": None,
                        "reasoning_steps": [
                            f"Step 1: Verified same entity ('{attr_a.get('entity')}').",
                            f"Step 2: Verified same metric ('{attr_a.get('metric')}').",
                            f"Step 3: Verified same target time period ('{attr_a.get('period')}').",
                            f"Step 4: Compared values: Doc A reports {val_a} vs Doc B reports {val_b}.",
                            "Conclusion: Genuine conflict detected — conflicting values reported for identical period and scope."
                        ],
                        "summary": f"Direct contradiction: Doc A reports {val_a} while Doc B reports {val_b} for {attr_a.get('period')}."
                    }
                }
        else:
            # Different periods -> Reconciled by Time Period
            confidence = _rule_confidence(
                same_entity=same_entity, same_metric=same_metric,
                same_period=same_period, same_unit=same_unit,
                same_scope=same_scope, numeric_evidence=num_a is not None and num_b is not None,
                base=0.40,
            )
            return {
                "relationship_type": "reconciled",
                "confidence": confidence,
                "reasoning": {
                    "same_entity": True,
                    "same_metric": True,
                    "same_period": False,
                    "same_unit": same_unit,
                    "same_scope": same_scope,
                    "reconciliation_dimension": "Time Period",
                    "reasoning_steps": [
                        f"Step 1: Verified same entity ('{attr_a.get('entity')}').",
                        f"Step 2: Verified same metric ('{attr_a.get('metric')}').",
                        f"Step 3: Detected different time periods: '{attr_a.get('period')}' vs '{attr_b.get('period')}'.",
                        f"Step 4: Values differ ({val_a} vs {val_b}), but this is expected as metric evolved over time.",
                        "Conclusion: Apparent contradiction reconciled by time period difference."
                    ],
                    "summary": f"Reconciled by Time Period: {val_a} reported for {attr_a.get('period')}, whereas {val_b} reported for {attr_b.get('period')}."
                }
            }

    # Default fallback. Explain the actual mismatch so the UI is useful and
    # so users can distinguish an entity mismatch from a metric/period issue.
    mismatch_reasons = []
    if not same_entity:
        mismatch_reasons.append(f"entity mismatch ({attr_a.get('entity')!r} vs {attr_b.get('entity')!r})")
    if not same_metric:
        mismatch_reasons.append(f"metric mismatch ({attr_a.get('metric')!r} vs {attr_b.get('metric')!r})")
    if not same_period:
        mismatch_reasons.append(f"period mismatch ({attr_a.get('period')!r} vs {attr_b.get('period')!r})")
    if not same_unit:
        mismatch_reasons.append(f"unit mismatch ({attr_a.get('unit')!r} vs {attr_b.get('unit')!r})")
    mismatch_summary = "; ".join(mismatch_reasons) or "insufficient comparable attributes"
    fallback_confidence = _rule_confidence(
        same_entity=same_entity, same_metric=same_metric,
        same_period=same_period, same_unit=same_unit,
        same_scope=same_scope, numeric_evidence=num_a is not None and num_b is not None,
        base=0.25,
    )
    return {
        "relationship_type": "uncertain",
        "confidence": fallback_confidence,
        "reasoning": {
            "same_entity": same_entity,
            "same_metric": same_metric,
            "same_period": same_period,
            "same_unit": False,
            "same_scope": False,
            "reconciliation_dimension": None,
            "reasoning_steps": [
                "Step 1: Evaluated candidate fact pair.",
                f"Step 2: {mismatch_summary}."
            ],
            "summary": f"Relationship is uncertain: {mismatch_summary}."
        }
    }
