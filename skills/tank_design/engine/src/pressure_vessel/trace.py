"""Calculation records: the audit trail behind every number.

Each record follows the chain the report prints:
Input -> Formula/Method -> Code Reference -> Intermediate Values -> Result ->
Acceptance Status. Records are plain data and serialise to JSON unchanged.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .status import RecordKind, Status, decide
from .units import fmt


@dataclass
class TraceValue:
    symbol: str
    value: Any
    unit: str = ""
    description: str = ""
    source: str = ""        # INPUT, DERIVED, MATERIAL:<id>, CODE_TABLE:<ref>, USER_SUPPLIED, ...

    def text(self, digits: int = 3) -> str:
        v = fmt(self.value, digits) if isinstance(self.value, (int, float)) and not isinstance(self.value, bool) else str(self.value)
        return f"{self.symbol} = {v} {self.unit}".rstrip()


@dataclass
class CalcRecord:
    calc_id: str
    component: str
    title: str
    kind: RecordKind = RecordKind.CHECK
    code_family: str = "ASME_VIII_1"
    method: str = ""
    references: list[str] = field(default_factory=list)
    inputs: list[TraceValue] = field(default_factory=list)
    formula: list[str] = field(default_factory=list)
    substitution: list[str] = field(default_factory=list)
    intermediates: list[TraceValue] = field(default_factory=list)
    results: list[TraceValue] = field(default_factory=list)
    criterion: str = ""
    criterion_met: bool | None = None
    status: Status | None = None
    status_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    mandatory: bool = True
    materials: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)   # what the user must supply to evaluate

    # -- building helpers -------------------------------------------------
    def inp(self, symbol, value, unit="", description="", source="INPUT"):
        self.inputs.append(TraceValue(symbol, value, unit, description, source))
        return value

    def mid(self, symbol, value, unit="", description="", source="DERIVED"):
        self.intermediates.append(TraceValue(symbol, value, unit, description, source))
        return value

    def res(self, symbol, value, unit="", description="", source="DERIVED"):
        self.results.append(TraceValue(symbol, value, unit, description, source))
        return value

    def eq(self, formula: str, substitution: str = ""):
        """Formula and its numeric substitution; the two lists stay aligned."""
        self.formula.append(formula)
        self.substitution.append(substitution)

    def value(self, symbol: str):
        for group in (self.results, self.intermediates, self.inputs):
            for tv in group:
                if tv.symbol == symbol:
                    return tv.value
        raise KeyError(symbol)

    # -- status -------------------------------------------------------------
    def finalize(self, *, unverified: list[str] | None = None, out_of_scope: str | None = None,
                 not_evaluated_reason: str | None = None) -> "CalcRecord":
        """Set the status from ``criterion_met`` and the data quality.

        ``unverified`` lists the data items (references, materials) that are not
        verified; a met criterion on such data becomes NEEDS_ENGINEERING_REVIEW."""
        if self.kind == RecordKind.COMPUTATION:
            self.status = None
            return self
        status, reasons = decide(self.criterion_met, unverified_items=unverified,
                                 out_of_scope=out_of_scope)
        if status == Status.NOT_EVALUATED and not_evaluated_reason:
            reasons = [not_evaluated_reason]
        self.status, self.status_reasons = status, self.status_reasons + reasons
        return self

    def to_dict(self) -> dict:
        d = asdict(self)
        d["kind"] = str(self.kind)
        d["status"] = None if self.status is None else str(self.status)
        return d

    @property
    def status_text(self) -> str:
        return "COMPUTED" if self.kind == RecordKind.COMPUTATION else str(self.status)


def record_from_dict(d: dict) -> CalcRecord:
    d = dict(d)
    for k in ("inputs", "intermediates", "results"):
        d[k] = [TraceValue(**tv) for tv in d.get(k, [])]
    d["kind"] = RecordKind(d.get("kind", "CHECK"))
    d["status"] = None if d.get("status") is None else Status(d["status"])
    return CalcRecord(**d)
