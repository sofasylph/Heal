"""Synthetic claim generator with ground-truth labels.

Generates (a) ground-truth claim facts, (b) realistic text documents rendered from
them (claim form, discharge summary, itemised bill), and (c) an expected outcome from
an independent reference calculator that works on the ground-truth facts, never on
extracted text. The eval therefore measures extraction + rule application end to end.

It does NOT validate that the policy interpretation itself is correct; that needs
human-labelled claims from domain experts (see docs/ROADMAP.md).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import StrEnum

from claimtrace.domain.models import BillCategory, Recommendation
from claimtrace.extraction.pipeline import RawDocument
from claimtrace.policies.models import Policy
from claimtrace.policies.registry import load_policies


class Scenario(StrEnum):
    CLEAN = "clean"
    ROOM_RENT_OVER_CAP = "room_rent_over_cap"
    SENIOR_COPAY = "senior_copay"
    PED_WITHIN_WAITING = "ped_within_waiting"
    PED_AFTER_WAITING = "ped_after_waiting"
    SPECIFIC_WAITING = "specific_waiting"
    INITIAL_WAITING = "initial_waiting"
    COSMETIC_EXCLUDED = "cosmetic_excluded"
    AMBIGUOUS_EXCLUSION = "ambiguous_exclusion"
    MISSING_DOCUMENT = "missing_document"
    CONFLICTING_DATES = "conflicting_dates"
    DUPLICATE_LINE = "duplicate_line"


SCENARIO_WEIGHTS = {
    Scenario.CLEAN: 0.26,
    Scenario.ROOM_RENT_OVER_CAP: 0.12,
    Scenario.SENIOR_COPAY: 0.08,
    Scenario.PED_WITHIN_WAITING: 0.07,
    Scenario.PED_AFTER_WAITING: 0.05,
    Scenario.SPECIFIC_WAITING: 0.07,
    Scenario.INITIAL_WAITING: 0.05,
    Scenario.COSMETIC_EXCLUDED: 0.05,
    Scenario.AMBIGUOUS_EXCLUSION: 0.06,
    Scenario.MISSING_DOCUMENT: 0.06,
    Scenario.CONFLICTING_DATES: 0.06,
    Scenario.DUPLICATE_LINE: 0.07,
}

CATALOG = [
    {
        "key": "appendectomy",
        "diagnosis": "Acute appendicitis",
        "procedure": "Laparoscopic appendectomy",
        "base": 95000,
        "los": 3,
        "surgical": True,
    },
    {
        "key": "cholecystectomy",
        "diagnosis": "Symptomatic cholelithiasis",
        "procedure": "Laparoscopic cholecystectomy",
        "base": 120000,
        "los": 3,
        "surgical": True,
    },
    {
        "key": "dengue",
        "diagnosis": "Dengue fever with thrombocytopenia",
        "procedure": "Medical management, platelet monitoring",
        "base": 60000,
        "los": 4,
        "surgical": False,
    },
    {
        "key": "pneumonia",
        "diagnosis": "Community acquired pneumonia",
        "procedure": "Medical management with IV antibiotics",
        "base": 80000,
        "los": 5,
        "surgical": False,
    },
    {
        "key": "angioplasty",
        "diagnosis": "Coronary artery disease, NSTEMI",
        "procedure": "PTCA with drug eluting stent",
        "base": 280000,
        "los": 3,
        "surgical": True,
        "implant": ("Coronary stent implant", 0.30),
    },
    {
        "key": "cataract",
        "diagnosis": "Senile cataract, right eye",
        "procedure": "Phacoemulsification with IOL",
        "base": 45000,
        "los": 1,
        "surgical": True,
        "implant": ("Intraocular lens implant", 0.25),
    },
    {
        "key": "knee",
        "diagnosis": "Primary osteoarthritis, right knee",
        "procedure": "Total knee replacement",
        "base": 320000,
        "los": 5,
        "surgical": True,
        "implant": ("Knee prosthesis implant", 0.35),
    },
]
HERNIA = {
    "key": "hernia",
    "diagnosis": "Right inguinal hernia",
    "procedure": "Laparoscopic hernioplasty with mesh",
    "base": 110000,
    "los": 3,
    "surgical": True,
}
PED_CASE = {
    "key": "diabetic_foot",
    "diagnosis": "Diabetic foot ulcer, left foot",
    "procedure": "Surgical debridement",
    "base": 90000,
    "los": 6,
    "surgical": True,
}
COSMETIC = {
    "key": "rhinoplasty",
    "diagnosis": "External nasal deformity",
    "procedure": "Cosmetic rhinoplasty",
    "base": 150000,
    "los": 2,
    "surgical": True,
}
AMBIGUOUS = {
    "key": "rhinoplasty",
    "diagnosis": "Nasal hump, patient request",
    "procedure": "Aesthetic nasal reshaping",
    "base": 150000,
    "los": 2,
    "surgical": True,
}

FIRST = [
    "Aarav",
    "Priya",
    "Rohan",
    "Ananya",
    "Vikram",
    "Meera",
    "Kabir",
    "Sneha",
    "Arjun",
    "Kavya",
    "Rahul",
    "Isha",
    "Aditya",
    "Neha",
    "Sanjay",
    "Pooja",
    "Farhan",
    "Lakshmi",
]
LAST = [
    "Sharma",
    "Iyer",
    "Patel",
    "Reddy",
    "Kulkarni",
    "Nair",
    "Gupta",
    "Khan",
    "Deshpande",
    "Menon",
    "Singh",
    "Joshi",
    "Rao",
    "Banerjee",
]
HOSPITALS = [
    "Sunrise Multispeciality Hospital, Pune",
    "Lotus Care Hospital, Bengaluru",
    "Greenfield Medical Centre, Hyderabad",
    "Riverside General Hospital, Mumbai",
    "Anand Healthcare, Ahmedabad",
]
DATE_FORMATS = ["%d/%m/%Y", "%d-%b-%Y", "%d %B %Y"]


@dataclass
class Line:
    description: str
    category: BillCategory
    amount: float
    days: int | None = None
    rate: float | None = None
    duplicate: bool = False


@dataclass
class TruthFacts:
    patient_name: str
    patient_age: int
    policy_number: str
    policy_start_date: date
    hospital: str
    diagnosis: str
    procedure: str
    admission_date: date
    discharge_date: date
    room_type: str
    pre_existing_conditions: list[str]
    lines: list[Line]

    @property
    def claimed_amount(self) -> float:
        return round(sum(li.amount for li in self.lines), 2)


@dataclass
class GroundTruth:
    recommendation: Recommendation
    payable_amount: float
    requires_human: bool = False  # ambiguous / conflicting: must not be auto-processed
    should_flag_anomaly: bool = False
    notes: str = ""


@dataclass
class SyntheticClaim:
    claim_id: str
    policy_id: str
    scenario: Scenario
    truth_facts: TruthFacts
    truth: GroundTruth
    documents: list[RawDocument] = field(default_factory=list)


def _amt(rng: random.Random, x: float) -> float:
    v = round(x + rng.uniform(-0.03, 0.03) * x)
    if v % 1000 == 0:
        v += 137
    return float(v)


def _lines(rng: random.Random, case: dict, los: int, rate: float) -> list[Line]:
    total = case["base"] * rng.uniform(0.85, 1.15)
    lines = [
        Line("Room Rent - Single Private", BillCategory.ROOM, rate * los, los, rate),
        Line("Nursing Charges", BillCategory.NURSING, _amt(rng, 700 * los)),
    ]
    if case["surgical"]:
        lines += [
            Line("OT Charges", BillCategory.PROCEDURE, _amt(rng, 0.30 * total)),
            Line("Surgeon Fee", BillCategory.SURGEON_FEE, _amt(rng, 0.15 * total)),
            Line("Anaesthetist Fee", BillCategory.SURGEON_FEE, _amt(rng, 0.05 * total)),
        ]
    else:
        lines.append(
            Line("Consultant Doctor Visits", BillCategory.SURGEON_FEE, _amt(rng, 0.20 * total))
        )
    lines += [
        Line("Pharmacy & Medicines", BillCategory.MEDICINES, _amt(rng, 0.12 * total)),
        Line("Laboratory Investigations", BillCategory.DIAGNOSTICS, _amt(rng, 0.08 * total)),
    ]
    if "implant" in case:
        name, share = case["implant"]
        lines.append(Line(name, BillCategory.IMPLANTS, _amt(rng, share * total)))
    if rng.random() < 0.7:
        lines.append(
            Line("Surgical Consumables", BillCategory.CONSUMABLES, _amt(rng, 0.03 * total))
        )
    if rng.random() < 0.3:
        fee = float(rng.choice([350, 750]))
        lines.append(Line("Registration Charges", BillCategory.OTHER, fee))
    return lines


# ---------------------------------------------------------------------------
# Reference calculator (independent of the rules engine)
# ---------------------------------------------------------------------------


def reference_payable(policy: Policy, tf: TruthFacts, procedure_key: str) -> float:
    r = policy.rules
    payable = {id(li): li.amount for li in tf.lines if not li.duplicate}
    for li in tf.lines:
        if li.duplicate:
            continue
        desc = li.description.lower()
        if li.category in r.non_payable_categories or any(
            k in desc for k in r.non_payable_keywords
        ):
            payable[id(li)] = 0.0
    room = next(li for li in tf.lines if li.category is BillCategory.ROOM)
    cap = r.room_rent_cap_per_day
    if cap and room.rate and room.rate > cap:
        payable[id(room)] = cap * room.days
        ratio = cap / room.rate
        for li in tf.lines:
            if not li.duplicate and li.category in r.proportionate_deduction_categories:
                payable[id(li)] = round(payable[id(li)] * ratio, 2)
    total = sum(payable.values())
    limits = {"cataract": "Cataract", "knee": "Joint replacement"}
    for sl in r.sublimits:
        if limits.get(procedure_key) == sl.name:
            total = min(total, sl.max_amount)
    total = min(total, r.sum_insured)
    total = max(total - r.deductible, 0)
    if r.copay_percent and (r.copay_min_age is None or tf.patient_age >= r.copay_min_age):
        total -= round(total * r.copay_percent / 100, 2)
    return round(total, 2)


# ---------------------------------------------------------------------------
# Document rendering
# ---------------------------------------------------------------------------


def _fmt(rng: random.Random, d: date) -> str:
    return d.strftime(rng.choice(DATE_FORMATS))


def _money(x: float) -> str:
    return f"{x:,.2f}"


def render_documents(rng: random.Random, tf: TruthFacts, scenario: Scenario) -> list[RawDocument]:
    ped = ", ".join(tf.pre_existing_conditions) or "None"
    cf_admission = tf.admission_date
    if scenario is Scenario.CONFLICTING_DATES:
        cf_admission = tf.admission_date - timedelta(days=2)
    name_label = rng.choice(["Insured Name", "Patient Name"])
    claim_form = "\n".join(
        [
            "HEALTH INSURANCE CLAIM FORM - PART A (Reimbursement)",
            f"Policy Number: {tf.policy_number}",
            f"{name_label}: {tf.patient_name}",
            f"Age: {tf.patient_age}",
            f"Policy Start Date: {_fmt(rng, tf.policy_start_date)}",
            f"Hospital Name: {tf.hospital}",
            f"Date of Admission: {_fmt(rng, cf_admission)}",
            f"Date of Discharge: {_fmt(rng, tf.discharge_date)}",
            f"Pre-existing Diseases: {ped}",
            f"Total Amount Claimed: INR {_money(tf.claimed_amount)}",
            "",
            "Declaration by Insured: I hereby declare that the information furnished is true.",
        ]
    )
    dx_label = rng.choice(["Final Diagnosis", "Diagnosis"])
    discharge = "\n".join(
        [
            f"{tf.hospital.upper()}",
            "DISCHARGE SUMMARY",
            f"Patient Name: {tf.patient_name}",
            f"Age: {tf.patient_age}",
            f"Date of Admission: {_fmt(rng, tf.admission_date)}",
            f"Date of Discharge: {_fmt(rng, tf.discharge_date)}",
            f"Room Category: {tf.room_type}",
            f"{dx_label}: {tf.diagnosis}",
            f"Procedure Performed: {tf.procedure}",
            "Course in Hospital: Patient was admitted, evaluated and managed as above. "
            "Recovery uneventful.",
            "Condition at Discharge: Stable.",
        ]
    )
    bill_lines = []
    for li in tf.lines:
        if li.days and li.rate:
            label = f"{li.description} ({li.days} days @ INR {li.rate:,.0f})"
        else:
            label = li.description
        bill_lines.append(f"{label} ........ {_money(li.amount)}")
    invoice = "\n".join(
        [
            f"{tf.hospital.upper()}",
            f"FINAL BILL / INVOICE    Bill No: FB-{rng.randint(10000, 99999)}",
            f"Patient Name: {tf.patient_name}",
            f"Room Category: {tf.room_type}",
            "",
            *bill_lines,
            "",
            f"Grand Total ........ {_money(tf.claimed_amount)}",
            f"Net Payable ........ {_money(tf.claimed_amount)}",
        ]
    )
    docs = [
        RawDocument(filename="claim_form.txt", text=claim_form),
        RawDocument(filename="discharge_summary.txt", text=discharge),
        RawDocument(filename="final_bill.txt", text=invoice),
    ]
    if scenario is Scenario.MISSING_DOCUMENT:
        docs = [d for d in docs if d.filename != "discharge_summary.txt"]
    return docs


# ---------------------------------------------------------------------------
# Scenario construction
# ---------------------------------------------------------------------------


def generate_claim(
    rng: random.Random, idx: int, scenario: Scenario, policy: Policy
) -> SyntheticClaim:
    r = policy.rules
    case = rng.choice(CATALOG)
    tenure_months = rng.randint(40, 80)
    age = rng.randint(25, 58)
    ped: list[str] = rng.choice([[], [], ["Hypertension"], ["Hypothyroidism"]])
    rate_cap = r.room_rent_cap_per_day
    rate = float(rng.choice([3500, 4200, 4800, 5000] if rate_cap else [6000, 8500, 12000]))
    truth_rec: Recommendation | None = None
    requires_human = False
    should_flag = False

    if scenario is Scenario.ROOM_RENT_OVER_CAP:
        if rate_cap:
            rate = float(rng.choice([7500, 9000, 10000]))
        else:  # no cap on this policy: over-cap is still payable, reference handles it
            rate = float(rng.choice([15000, 18000]))
        case = rng.choice([c for c in CATALOG if c["key"] not in ("cataract", "knee")])
    elif scenario is Scenario.SENIOR_COPAY:
        age = rng.randint(61, 75)
    elif scenario is Scenario.PED_WITHIN_WAITING:
        case, ped = PED_CASE, ["Type 2 Diabetes Mellitus"]
        tenure_months = rng.randint(6, r.ped_waiting_months - 2)
        truth_rec = Recommendation.NOT_PAYABLE
    elif scenario is Scenario.PED_AFTER_WAITING:
        case, ped = PED_CASE, ["Type 2 Diabetes Mellitus"]
        tenure_months = r.ped_waiting_months + rng.randint(2, 20)
    elif scenario is Scenario.SPECIFIC_WAITING:
        case = HERNIA
        hernia_wait = next(w.months for w in r.specific_waiting_periods if w.name == "Hernia")
        tenure_months = rng.randint(3, hernia_wait - 2)
        truth_rec = Recommendation.NOT_PAYABLE
    elif scenario is Scenario.INITIAL_WAITING:
        case = next(c for c in CATALOG if c["key"] == "dengue")
        tenure_months = 0
        truth_rec = Recommendation.NOT_PAYABLE
    elif scenario is Scenario.COSMETIC_EXCLUDED:
        case = COSMETIC
        truth_rec = Recommendation.NOT_PAYABLE
    elif scenario is Scenario.AMBIGUOUS_EXCLUSION:
        case = AMBIGUOUS
        truth_rec = Recommendation.NOT_PAYABLE
        requires_human = True
    elif scenario is Scenario.MISSING_DOCUMENT:
        truth_rec = Recommendation.NEEDS_INFO
    elif scenario is Scenario.CONFLICTING_DATES:
        requires_human = True
        case = rng.choice([c for c in CATALOG if c["key"] not in ("cataract", "knee")])
    elif scenario is Scenario.DUPLICATE_LINE:
        requires_human = True
        should_flag = True

    los = case["los"] + rng.choice([0, 0, 1])
    admission = date(2025, 1, 1) + timedelta(days=rng.randint(0, 540))
    if scenario is Scenario.INITIAL_WAITING:
        start = admission - timedelta(days=rng.randint(5, r.initial_waiting_days - 5))
    else:
        start = _months_before(admission, tenure_months, rng)
    lines = _lines(rng, case, los, rate)
    if scenario is Scenario.DUPLICATE_LINE:
        dup = next(li for li in lines if li.category is BillCategory.DIAGNOSTICS)
        lines.append(Line(dup.description, dup.category, dup.amount, duplicate=True))

    tf = TruthFacts(
        patient_name=f"{rng.choice(FIRST)} {rng.choice(LAST)}",
        patient_age=age,
        policy_number=f"{policy.policy_id[:3]}/{rng.randint(100000, 999999)}/{admission.year}",
        policy_start_date=start,
        hospital=rng.choice(HOSPITALS),
        diagnosis=case["diagnosis"],
        procedure=case["procedure"],
        admission_date=admission,
        discharge_date=admission + timedelta(days=los),
        room_type="Single Private AC",
        pre_existing_conditions=ped,
        lines=lines,
    )
    if truth_rec in (Recommendation.NOT_PAYABLE, Recommendation.NEEDS_INFO):
        payable = 0.0
    else:
        payable = reference_payable(policy, tf, case["key"])
        truth_rec = (
            Recommendation.PAY if payable >= tf.claimed_amount - 0.5 else Recommendation.PARTIAL
        )
    truth = GroundTruth(
        recommendation=truth_rec,
        payable_amount=payable,
        requires_human=requires_human,
        should_flag_anomaly=should_flag,
    )
    claim = SyntheticClaim(
        claim_id=f"CLM-{idx:04d}",
        policy_id=policy.policy_id,
        scenario=scenario,
        truth_facts=tf,
        truth=truth,
    )
    claim.documents = render_documents(rng, tf, scenario)
    return claim


def _months_before(d: date, months: int, rng: random.Random) -> date:
    y, m = divmod(d.month - 1 - months, 12)
    return date(d.year + y, m + 1, min(d.day, 28)) - timedelta(days=rng.randint(0, 20))


def generate_dataset(n: int = 200, seed: int = 7) -> list[SyntheticClaim]:
    rng = random.Random(seed)
    policies = list(load_policies().values())
    scenarios = list(SCENARIO_WEIGHTS)
    weights = [SCENARIO_WEIGHTS[s] for s in scenarios]
    out = []
    for i in range(1, n + 1):
        scenario = rng.choices(scenarios, weights)[0]
        policy = rng.choice(policies)
        if scenario is Scenario.AMBIGUOUS_EXCLUSION:
            # Only policies whose exclusions list the related terms make this ambiguous.
            policy = next(p for p in policies if p.policy_id == "SURAKSHA-SILVER")
        out.append(generate_claim(rng, i, scenario, policy))
    return out
