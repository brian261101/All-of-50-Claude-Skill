"""ASME VIII-1 calculation entry points — intentionally blocked scaffold."""
from tankvessel.calculations.base import blocked_result

def shell_internal_pressure(inputs):
    """Return BLOCKED until code edition, method and validation evidence are configured."""
    return blocked_result(
        "ASME-001", "ASME_VIII_1_SHELL_INTERNAL_PRESSURE",
        inputs=inputs,
        reason="BLOCKED: add an authorized code reference, verified method, material data and independent regression cases.",
    )

def head_thickness(inputs):
    return blocked_result(
        "ASME-002", "ASME_VIII_1_HEAD_THICKNESS",
        inputs=inputs,
        reason="BLOCKED: head type, applicable code method, authorized reference and independent validation are required.",
    )

def nozzle_reinforcement(inputs):
    return blocked_result(
        "ASME-003", "ASME_VIII_1_NOZZLE_REINFORCEMENT",
        inputs=inputs,
        reason="BLOCKED: nozzle geometry, applicable code method, source data and independent validation are required.",
    )
