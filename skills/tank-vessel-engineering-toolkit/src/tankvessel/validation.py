"""Input validation helpers. These validate structure only, not code compliance."""
from typing import Any, Dict, List

SUPPORTED_ROUTES = {
    ("PRESSURE_VESSEL", "ASME_VIII_1"),
    ("API650_STORAGE_TANK", "API_650"),
}

def validate_route(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    equipment = data.get("equipment") or {}
    code = data.get("code") or {}
    route = (equipment.get("category"), code.get("family"))
    if route not in SUPPORTED_ROUTES:
        errors.append(
            "Equipment/code route is missing, inconsistent, or unsupported: "
            f"category={route[0]!r}, family={route[1]!r}. "
            "Use PRESSURE_VESSEL + ASME_VIII_1 or API650_STORAGE_TANK + API_650."
        )
    if not code.get("edition"):
        errors.append("Exact code edition is required; do not infer a default.")
    if not (data.get("project") or {}).get("units"):
        errors.append("Explicit project units are required.")
    return errors

def validate_positive_if_present(data: Dict[str, Any], dotted_paths) -> List[str]:
    errors: List[str] = []
    for dotted in dotted_paths:
        current: Any = data
        for part in dotted.split("."):
            if not isinstance(current, dict) or part not in current:
                current = None
                break
            current = current[part]
        if current is not None:
            try:
                if float(current) <= 0:
                    errors.append(f"{dotted} must be greater than zero when provided.")
            except (TypeError, ValueError):
                errors.append(f"{dotted} must be numeric when provided.")
    return errors
