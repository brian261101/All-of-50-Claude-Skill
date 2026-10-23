"""Code reference register with per-project verification state."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .paths import DATA_DIR


@dataclass
class CodeReference:
    id: str
    family: str
    document: str
    clause: str
    title: str
    used_for: str = ""
    edition_basis: str = ""
    cited_by: str = ""
    verification_status: str = "UNVERIFIED"
    verified_by: str | None = None
    verified_on: str | None = None
    verified_edition: str | None = None
    remark: str = ""

    @property
    def verified(self) -> bool:
        return self.verification_status == "VERIFIED"

    def label(self) -> str:
        return f"{self.document.replace('ASME BPVC Section VIII Division 1', 'ASME VIII-1')} {self.clause}"


class ReferenceRegister:
    def __init__(self, entries: dict[str, CodeReference], version: str):
        self.entries = entries
        self.version = version

    @classmethod
    def load(cls, path: Path | None = None, verification: dict | list | None = None) -> "ReferenceRegister":
        data = json.loads(Path(path or DATA_DIR / "code_references.json").read_text(encoding="utf-8"))
        entries = {}
        for e in data["entries"]:
            known = {k: v for k, v in e.items() if k in CodeReference.__dataclass_fields__}
            entries[e["id"]] = CodeReference(**known)
        reg = cls(entries, data.get("register_version", "?"))
        if verification:
            reg.apply_verification(verification)
        return reg

    def apply_verification(self, items) -> list[str]:
        """Mark entries verified from a project file. Each item needs id,
        verified_by, verified_on and edition; anything incomplete is refused."""
        if isinstance(items, dict):
            items = items.get("verified", [])
        problems = []
        for it in items or []:
            rid = it.get("id")
            if rid not in self.entries:
                problems.append(f"unknown reference id {rid!r}")
                continue
            missing = [k for k in ("verified_by", "verified_on", "edition") if not it.get(k)]
            if missing:
                problems.append(f"{rid}: verification needs {missing}")
                continue
            ref = self.entries[rid]
            ref.verification_status = "VERIFIED"
            ref.verified_by, ref.verified_on = str(it["verified_by"]), str(it["verified_on"])
            ref.verified_edition = str(it["edition"])
            ref.remark = str(it.get("remark", ""))
        return problems

    def get(self, rid: str) -> CodeReference:
        if rid not in self.entries:
            raise KeyError(f"code reference {rid!r} is not in the register; add it before citing it")
        return self.entries[rid]

    def unverified(self, ids) -> list[str]:
        return [f"code reference {rid} not verified" for rid in ids if not self.get(rid).verified]

    def summary(self, used_ids) -> dict:
        used = sorted(set(used_ids))
        return {"register_version": self.version, "used": len(used),
                "verified": sum(self.get(r).verified for r in used),
                "unverified_ids": [r for r in used if not self.get(r).verified]}
