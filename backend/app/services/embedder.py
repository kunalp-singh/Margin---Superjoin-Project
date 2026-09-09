import logging
import math
import re
from difflib import SequenceMatcher
from typing import List, Dict, Any, Tuple
import numpy as np
from backend.app.config import CANDIDATE_SIMILARITY_THRESHOLD, TOP_K_CANDIDATES

logger = logging.getLogger(__name__)


def _fallback_vectorize(text: str, dim: int = 384) -> List[float]:
    """
    Fast, deterministic feature vectorizer for normalized subject signatures.
    Uses hash-based n-gram embedding vector with unit L2 normalization.
    """
    if not text:
        return [0.0] * dim

    vec = np.zeros(dim, dtype=np.float32)
    tokens = re.findall(r'\w+', text.lower())
    
    # Unigrams and bigrams hashing
    for i, token in enumerate(tokens):
        h1 = hash(token) % dim
        vec[h1] += 1.0
        if i < len(tokens) - 1:
            bigram = f"{token}_{tokens[i+1]}"
            h2 = hash(bigram) % dim
            vec[h2] += 1.5

    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec.tolist()


def generate_embedding(text: str) -> List[float]:
    """
    Generates a normalized embedding vector for a normalized signature text.
    """
    return _fallback_vectorize(text)


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Computes cosine similarity between two normalized vector lists.
    """
    v1 = np.array(vec1, dtype=np.float32)
    v2 = np.array(vec2, dtype=np.float32)
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(np.dot(v1, v2) / (norm1 * norm2))


def _dimension(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def is_compatible_candidate(new_fact: Dict[str, Any], existing_fact: Dict[str, Any]) -> bool:
    """Block semantic neighbors that cannot be meaningfully compared.

    Period and scope differences are retained because they are useful
    reconciliation evidence. Entity and metric are hard comparability keys;
    missing keys are not silently treated as equal.
    """
    left, right = new_fact.get("attributes") or {}, existing_fact.get("attributes") or {}
    entity_a, entity_b = _dimension(left.get("entity")), _dimension(right.get("entity"))
    metric_a, metric_b = _dimension(left.get("metric")), _dimension(right.get("metric"))
    if not entity_a or not entity_b or not metric_a or not metric_b:
        return False
    if entity_a != entity_b and entity_a not in entity_b and entity_b not in entity_a:
        return False
    if metric_a != metric_b and not (
        ("revenue" in metric_a and "revenue" in metric_b)
        or ("margin" in metric_a and "margin" in metric_b)
        or ("headcount" in metric_a and "headcount" in metric_b)
    ):
        return False
    if new_fact.get("status") == "uncertain" or existing_fact.get("status") == "uncertain":
        return False
    return True


def find_top_candidates(
    new_fact: Dict[str, Any],
    existing_facts: List[Dict[str, Any]],
    top_k: int = TOP_K_CANDIDATES,
    threshold: float = CANDIDATE_SIMILARITY_THRESHOLD
) -> List[Tuple[Dict[str, Any], float]]:
    """
    Searches existing facts for nearest candidate matches using embedding cosine similarity.
    Returns list of (existing_fact, similarity_score).
    """
    new_emb = new_fact.get("embedding")
    if not new_emb:
        new_emb = generate_embedding(new_fact.get("normalized_signature", ""))

    # Convert the query once instead of allocating arrays for every candidate.
    query = np.asarray(new_emb, dtype=np.float32)
    query_norm = np.linalg.norm(query)
    if query_norm == 0:
        return []

    candidates = []
    for fact in existing_facts:
        if fact["id"] == new_fact.get("id"):
            continue
        if not is_compatible_candidate(new_fact, fact):
            continue

        ex_emb = fact.get("embedding")
        if not ex_emb:
            continue

        ex = np.asarray(ex_emb, dtype=np.float32)
        ex_norm = np.linalg.norm(ex)
        if ex_norm == 0:
            continue
        sim = float(np.dot(query, ex) / (query_norm * ex_norm))
        if sim >= threshold:
            candidates.append((fact, sim))

    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[:top_k]


def _unit_kind(value: Any, unit: Any) -> str:
    raw = f"{value or ''} {unit or ''}".lower()
    if "%" in raw or "percent" in raw or "pct" in raw:
        return "percent"
    if any(token in raw for token in ("usd", "inr", "eur", "₹", "$", "currency", "crore", "million", "billion")):
        return "currency"
    if "day" in raw:
        return "duration"
    if raw.strip():
        return "count"
    return "unknown"


def is_compatible_candidate(new_fact: Dict[str, Any], existing_fact: Dict[str, Any]) -> bool:
    """Cheap hard gate before embedding retrieval and relationship classification."""
    if new_fact.get("status") != "normal" or existing_fact.get("status") != "normal":
        return False
    new_attrs = new_fact.get("attributes") or {}
    existing_attrs = existing_fact.get("attributes") or {}
    new_kind = _unit_kind(new_attrs.get("value"), new_attrs.get("unit"))
    existing_kind = _unit_kind(existing_attrs.get("value"), existing_attrs.get("unit"))
    if "unknown" not in {new_kind, existing_kind} and new_kind != existing_kind:
        return False

    new_metric = re.sub(r"[^a-z0-9]+", " ", str(new_attrs.get("metric", "")).lower()).strip()
    existing_metric = re.sub(r"[^a-z0-9]+", " ", str(existing_attrs.get("metric", "")).lower()).strip()
    if not new_metric or not existing_metric:
        return False
    if ("composition" in new_metric) != ("composition" in existing_metric):
        return False
    return SequenceMatcher(None, new_metric, existing_metric).ratio() >= 0.55
