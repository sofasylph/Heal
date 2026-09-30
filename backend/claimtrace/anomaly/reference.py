"""Reference statistics per procedure used for anomaly scoring.

Synthetic, order-of-magnitude figures for Indian private hospitals (INR). In a real
deployment these would be learned from historical claims per city tier and hospital.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProcedureProfile:
    name: str
    keywords: tuple[str, ...]
    mean_cost: float
    std_cost: float
    typical_los: int


PROFILES: list[ProcedureProfile] = [
    ProcedureProfile("Cataract", ("cataract", "phacoemulsification"), 45000, 12000, 1),
    ProcedureProfile("Appendectomy", ("appendectomy", "appendicectomy"), 95000, 25000, 3),
    ProcedureProfile("Hernia repair", ("hernia", "hernioplasty"), 110000, 30000, 3),
    ProcedureProfile("Knee replacement", ("knee replacement", "arthroplasty"), 320000, 60000, 5),
    ProcedureProfile("Cholecystectomy", ("cholecystectomy",), 120000, 30000, 3),
    ProcedureProfile("Dengue management", ("dengue",), 60000, 20000, 4),
    ProcedureProfile("Pneumonia management", ("pneumonia",), 80000, 25000, 5),
    ProcedureProfile("Angioplasty", ("angioplasty", "ptca"), 280000, 70000, 3),
    ProcedureProfile("Diabetic foot care", ("diabetic foot",), 90000, 30000, 6),
    ProcedureProfile("Rhinoplasty", ("rhinoplasty",), 150000, 40000, 2),
]
DEFAULT_PROFILE = ProcedureProfile("General admission", (), 90000, 45000, 4)


def profile_for(text: str | None) -> ProcedureProfile:
    t = (text or "").lower()
    for p in PROFILES:
        if any(k in t for k in p.keywords):
            return p
    return DEFAULT_PROFILE
