from dataclasses import dataclass, asdict
from typing import Any, Dict
from tankvessel.status import Status

@dataclass
class CalculationResult:
    calculation_id: str
    status: Status
    method_id: str
    message: str
    inputs: Dict[str, Any]
    results: Dict[str, Any]
    references: Dict[str, str]

    def to_dict(self):
        result = asdict(self)
        result["status"] = self.status.value
        return result

def blocked_result(calculation_id: str, method_id: str, inputs=None, reason=None):
    return CalculationResult(
        calculation_id=calculation_id,
        status=Status.BLOCKED,
        method_id=method_id,
        message=reason or (
            "No independently verified implementation and source reference is configured. "
            "No engineering result was calculated."
        ),
        inputs=inputs or {},
        results={},
        references={},
    )
