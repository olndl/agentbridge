from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Tuple


def flatten_keys(payload: Dict[str, Any], prefix: str = "") -> List[str]:
    keys: List[str] = []
    for key, value in payload.items():
        dotted = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            keys.extend(flatten_keys(value, dotted))
        else:
            keys.append(dotted)
    return keys


def get_path(payload: Dict[str, Any], path: str) -> Any:
    value: Any = payload
    for part in path.split("."):
        if isinstance(value, list) and part.isdigit():
            index = int(part)
            value = value[index] if index < len(value) else None
            continue
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def apply_mapping(payload: Dict[str, Any], mapping: Dict[str, str]) -> Dict[str, Any]:
    return {
        target_field: get_path(payload, source_path)
        for target_field, source_path in mapping.items()
    }


def suggest_mapping(
    sample_payload: Dict[str, Any], target_schema: Dict[str, Any]
) -> Tuple[Dict[str, str], List[str], List[str]]:
    source_fields = flatten_keys(sample_payload)
    target_fields = list(target_schema.keys())
    mapping: Dict[str, str] = {}

    for target in target_fields:
        best_source = _best_match(target, source_fields)
        if best_source:
            mapping[target] = best_source

    return mapping, source_fields, target_fields


def _best_match(target: str, source_fields: Iterable[str]) -> str:
    normalized_target = _normalize(target)
    ranked = sorted(
        (
            (_score(normalized_target, _normalize(source)), source)
            for source in source_fields
        ),
        reverse=True,
    )
    if not ranked:
        return ""

    score, source = ranked[0]
    return source if score >= 0.34 else ""


def _score(target: str, source: str) -> float:
    source_leaf = source.split(".")[-1]
    direct = SequenceMatcher(None, target, source_leaf).ratio()
    full_path = SequenceMatcher(None, target, source).ratio()
    contains = 0.25 if target in source or source_leaf in target else 0
    return max(direct, full_path) + contains


def _normalize(value: str) -> str:
    return value.lower().replace("_", "").replace("-", "").replace(" ", "")
