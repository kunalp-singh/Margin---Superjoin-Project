import re
from typing import List, Dict, Any, Optional
import fitz  # PyMuPDF


def _table_regions(page) -> List[Dict[str, Any]]:
    """Return table regions when the installed PyMuPDF exposes table finding.

    Table finding is optional across PyMuPDF releases.  A failed detector is
    deliberately represented as an uncertain table instead of aborting the
    document pipeline.
    """
    finder = getattr(page, "find_tables", None)
    if not finder:
        return []
    try:
        found = finder()
        tables = getattr(found, "tables", found or [])
        regions = []
        for table in tables:
            bbox_value = getattr(table, "bbox", None)
            if bbox_value is None and isinstance(table, dict):
                bbox_value = table.get("bbox", [])
            bbox = list(bbox_value or [])
            extract = getattr(table, "extract", None)
            rows = extract() if callable(extract) else (table.get("rows", []) if isinstance(table, dict) else [])
            regions.append({
                "bbox": bbox,
                "rows": rows or [],
                "status": "normal" if rows else "malformed",
            })
        return regions
    except Exception as exc:
        return [{"bbox": [], "rows": [], "status": "malformed", "error": str(exc)}]


def _layout_blocks(page, page_text: str) -> List[Dict[str, Any]]:
    """Keep text geometry so downstream extraction can validate its source."""
    blocks: List[Dict[str, Any]] = []
    cursor = 0
    try:
        raw_blocks = page.get_text("dict").get("blocks", [])
        for raw in raw_blocks:
            if raw.get("type") != 0:
                continue
            text = "\n".join(
                span.get("text", "")
                for line in raw.get("lines", [])
                for span in line.get("spans", [])
            ).strip()
            if not text:
                continue
            start = page_text.find(text, cursor)
            if start < 0:
                start = cursor
            end = start + len(text)
            cursor = end
            blocks.append({
                "text": text,
                "bbox": list(raw.get("bbox", [])),
                "char_start": start,
                "char_end": end,
            })
    except Exception:
        return []
    return blocks


def validate_statement_position(
    statement: Dict[str, Any],
    page_text: str,
    page_height: Optional[float] = None,
) -> bool:
    """Check that offsets and quotes point at the exact page text."""
    start, end = statement.get("char_start"), statement.get("char_end")
    quote = statement.get("statement", "")
    if page_height and statement.get("layout_block"):
        bbox = statement["layout_block"].get("bbox", [])
        if len(bbox) == 4:
            top_margin = page_height * 0.08
            bottom_margin = page_height * 0.92
            if bbox[3] <= top_margin or bbox[1] >= bottom_margin:
                return False
    return (
        isinstance(start, int) and isinstance(end, int)
        and 0 <= start <= end <= len(page_text)
        and page_text[start:end].strip() == quote.strip()
    )


def parse_pdf(file_path: str) -> Dict[str, Any]:
    """
    Parses a PDF file using PyMuPDF (fitz).
    Returns total page count and structured list of pages with text blocks and segmented candidate statements.
    """
    doc = fitz.open(file_path)
    page_count = len(doc)
    pages_data = []

    for page_index in range(page_count):
        page = doc.load_page(page_index)
        page_num = page_index + 1
        page_text = page.get_text("text")
        page_height = float(page.rect.height)

        # Clean text basic whitespace normalization while preserving content
        normalized_text = page_text.strip()
        
        # Segment into candidate statements (sentences or coherent text clauses)
        layout_blocks = _layout_blocks(page, normalized_text)
        tables = _table_regions(page)
        statements = segment_text_into_statements(normalized_text, page_num)
        detector_failed = any(table.get("status") == "malformed" and not table.get("bbox") for table in tables)
        for statement in statements:
            statement["layout_block"] = next(
                (
                    {"bbox": block["bbox"], "char_start": block["char_start"], "char_end": block["char_end"]}
                    for block in layout_blocks
                    if block["char_start"] <= statement["char_start"] < block["char_end"]
                ),
                None,
            )
            statement["position_valid"] = validate_statement_position(
                statement, normalized_text, page_height
            )
            matching_tables = [
                table for table in tables
                if _bbox_overlaps((statement.get("layout_block") or {}).get("bbox", []), table.get("bbox", []))
            ]
            statement["is_table"] = bool(matching_tables)
            statement["table_status"] = (
                "malformed" if any(table.get("status") == "malformed" for table in matching_tables)
                else "normal" if matching_tables else None
            )
            if detector_failed and re.search(r"\d", statement["statement"]):
                statement["table_status"] = "malformed"

        pages_data.append({
            "page_number": page_num,
            "raw_text": normalized_text,
            "statements": statements,
            "blocks": layout_blocks,
            "tables": tables,
        })

    doc.close()
    return {
        "page_count": page_count,
        "pages": pages_data
    }


def _bbox_overlaps(first: List[float], second: List[float]) -> bool:
    if len(first) != 4 or len(second) != 4:
        return False
    return not (first[2] <= second[0] or second[2] <= first[0] or first[3] <= second[1] or second[3] <= first[1])


def segment_text_into_statements(text: str, page_number: int) -> List[Dict[str, Any]]:
    """
    Splits page text into candidate factual statements while keeping character start/end offsets.
    """
    if not text:
        return []

    # Split sentence boundaries and semicolon/bullet clauses while retaining
    # exact offsets.  Atomic clauses prevent a multi-value sentence/table from
    # becoming one unverifiable fact.
    sentence_end_pattern = re.compile(r'(?<!\b[A-Z])(?<!\b[a-z])(?<=[.!?])\s+(?=[A-Z0-9"])')
    raw_chunks = sentence_end_pattern.split(text)
    statements = []
    
    current_offset = 0
    for chunk in raw_chunks:
        chunk_clean = chunk.strip()
        # Find exact start and end offset in page text
        start_idx = text.find(chunk, current_offset)
        if start_idx == -1:
            start_idx = current_offset
        end_idx = start_idx + len(chunk)
        current_offset = end_idx

        # A clause's range is always a direct substring of the page text.
        clause_pattern = re.compile(r"[^;•]+(?:;|$)", re.DOTALL)
        for clause_match in clause_pattern.finditer(chunk):
            clause = clause_match.group(0)
            clause_clean = clause.strip(" \t\r\n;•")
            if len(clause_clean) < 10:
                continue
            clause_start = start_idx + clause_match.start() + len(clause) - len(clause.lstrip())
            clause_end = clause_start + len(clause_clean)
            statements.append({
                "statement": clause_clean,
                "char_start": clause_start,
                "char_end": clause_end,
                "page_number": page_number,
            })

    return statements
