"""API 650 calculation entry points — intentionally blocked scaffold."""
from tankvessel.calculations.base import blocked_result

def shell_courses(inputs):
    return blocked_result(
        "API-001", "API_650_SHELL_COURSES",
        inputs=inputs,
        reason="BLOCKED: add the exact API 650 edition, authorized method/material data and independently checked regression cases.",
    )

def bottom_annular_plate(inputs):
    return blocked_result(
        "API-002", "API_650_BOTTOM_ANNULAR_PLATE",
        inputs=inputs,
        reason="BLOCKED: tank geometry, applicability, authorized code method and independent validation are required.",
    )

def roof_design(inputs):
    return blocked_result(
        "API-003", "API_650_ROOF_DESIGN",
        inputs=inputs,
        reason="BLOCKED: roof type, applicable method, code edition and independent validation are required.",
    )
