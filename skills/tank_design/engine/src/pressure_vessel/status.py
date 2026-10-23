"""Result statuses, record kinds and design stages.

A check is only PASS when its acceptance criterion is met AND every piece of
data it relied on (code references, material data) is verified. A met criterion
on unverified data is NEEDS_ENGINEERING_REVIEW, never PASS. A computation with
no acceptance criterion (a weight, a reaction) has no status at all and is
shown as COMPUTED, so it cannot be mistaken for a passed check.
"""

from __future__ import annotations

from enum import Enum


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_EVALUATED = "NOT_EVALUATED"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    NEEDS_ENGINEERING_REVIEW = "NEEDS_ENGINEERING_REVIEW"

    def __str__(self) -> str:  # json/report friendly
        return self.value


# Aggregation order: the first status present wins.
_SEVERITY = [Status.FAIL, Status.OUT_OF_SCOPE, Status.NOT_EVALUATED,
             Status.NEEDS_ENGINEERING_REVIEW, Status.PASS]


def aggregate(statuses) -> Status | None:
    """Worst-case status of a group of checks (None if the group is empty)."""
    present = {Status(s) for s in statuses if s is not None}
    for s in _SEVERITY:
        if s in present:
            return s
    return None


class RecordKind(str, Enum):
    CHECK = "CHECK"              # has an acceptance criterion and a status
    COMPUTATION = "COMPUTATION"  # produces values only; displayed as COMPUTED

    def __str__(self) -> str:
        return self.value


class DesignStage(str, Enum):
    """Package maturity. Software can reach CALCULATION_VERIFIED at most; the
    two later stages are recorded from a signed human review file and are
    never set automatically."""

    PRELIMINARY = "PRELIMINARY"
    CALCULATION_VERIFIED = "CALCULATION_VERIFIED"
    ENGINEERING_REVIEW = "ENGINEERING_REVIEW"
    APPROVED_FOR_FABRICATION = "APPROVED_FOR_FABRICATION"

    def __str__(self) -> str:
        return self.value


class DataStatus(str, Enum):
    """Verification state of a material record or other engineering data."""

    VERIFIED_OFFICIAL = "VERIFIED_OFFICIAL"            # checked against the licensed source
    USER_SUPPLIED_VERIFIED = "USER_SUPPLIED_VERIFIED"  # supplied and signed off by the user
    USER_SUPPLIED_UNVERIFIED = "USER_SUPPLIED_UNVERIFIED"
    REPRESENTATIVE_EXAMPLE = "REPRESENTATIVE_EXAMPLE"  # demo/teaching values
    UNVERIFIED = "UNVERIFIED"

    def __str__(self) -> str:
        return self.value

    @property
    def release_eligible(self) -> bool:
        return self in (DataStatus.VERIFIED_OFFICIAL, DataStatus.USER_SUPPLIED_VERIFIED)


def decide(criterion_met: bool | None, *, unverified_items: list[str] | None = None,
           out_of_scope: str | None = None) -> tuple[Status, list[str]]:
    """Map an evaluated criterion and the data quality behind it to a status."""
    if out_of_scope:
        return Status.OUT_OF_SCOPE, [out_of_scope]
    if criterion_met is None:
        return Status.NOT_EVALUATED, []
    if not criterion_met:
        return Status.FAIL, []
    if unverified_items:
        return Status.NEEDS_ENGINEERING_REVIEW, [
            "criterion met arithmetically, but relies on unverified data: "
            + "; ".join(unverified_items)]
    return Status.PASS, []
