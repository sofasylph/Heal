"""Heuristic field extraction from claim document text.

Each field has a list of label patterns (canonical first). Values are collected from
every document, reconciled, and scored:
  * canonical label in the expected document type  -> 0.97
  * synonym label / unexpected document type       -> lower
  * documents disagree                             -> 0.5 and recorded as a conflict
The LLM extractor (see extraction/llm.py) plugs in behind the same output model.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from dateutil import parser as dateparser

from claimtrace.domain.models import (
    BillCategory,
    BillLineItem,
    ClaimDocument,
    ClaimFacts,
    DocumentType,
)

SEP = r"\s*:\s*"


@dataclass(frozen=True)
class FieldSpec:
    name: str
    labels: list[str]
    parse: Callable[[str], object]
    preferred_docs: tuple[DocumentType, ...]


def _date(v: str) -> date:
    return dateparser.parse(v.strip(), dayfirst=True).date()


def _money(v: str) -> float:
    return float(re.sub(r"[^\d.]", "", v.replace(",", "")))


def _int(v: str) -> int:
    return int(re.search(r"\d+", v).group())


def _text(v: str) -> str:
    return v.strip().rstrip(".")


def _list(v: str) -> list[str]:
    v = v.strip()
    if v.lower() in {"none", "nil", "na", "n/a", "-", "no"}:
        return []
    return [x.strip() for x in re.split(r"[,;]", v) if x.strip()]


CF, DS, INV = DocumentType.CLAIM_FORM, DocumentType.DISCHARGE_SUMMARY, DocumentType.INVOICE

FIELDS: list[FieldSpec] = [
    FieldSpec("patient_name", ["patient name", "name of patient", "insured name"], _text, (CF, DS)),
    FieldSpec("patient_age", ["age", "patient age"], _int, (CF, DS)),
    FieldSpec("policy_number", ["policy number", "policy no"], _text, (CF,)),
    FieldSpec(
        "policy_start_date",
        ["policy start date", "first policy inception date", "policy inception"],
        _date,
        (CF,),
    ),
    FieldSpec("hospital", ["hospital name", "name of hospital", "hospital"], _text, (CF, DS)),
    FieldSpec("diagnosis", ["final diagnosis", "diagnosis", "provisional diagnosis"], _text, (DS,)),
    FieldSpec(
        "procedure",
        ["procedure performed", "surgery performed", "procedure", "treatment given"],
        _text,
        (DS,),
    ),
    FieldSpec(
        "admission_date", ["date of admission", "admission date", "admitted on"], _date, (DS, CF)
    ),
    FieldSpec(
        "discharge_date", ["date of discharge", "discharge date", "discharged on"], _date, (DS, CF)
    ),
    FieldSpec("room_type", ["room category", "room type", "ward"], _text, (DS, INV)),
    FieldSpec(
        "pre_existing_conditions",
        ["pre-existing diseases", "pre-existing conditions", "declared ped", "past history"],
        _list,
        (CF,),
    ),
    FieldSpec(
        "claimed_amount", ["total amount claimed", "amount claimed", "claim amount"], _money, (CF,)
    ),
]

CATEGORY_KEYWORDS: list[tuple[BillCategory, tuple[str, ...]]] = [
    (BillCategory.ICU, ("icu", "intensive care")),
    (BillCategory.ROOM, ("room rent", "ward charges", "accommodation", "room charges")),
    (BillCategory.CONSUMABLES, ("consumable", "gloves", "mask", "disposable")),
    (BillCategory.IMPLANTS, ("implant", "intraocular lens", "iol", "prosthesis", "stent")),
    (
        BillCategory.SURGEON_FEE,
        ("surgeon", "anaesthetist", "anesthetist", "consultant fee", "doctor visit"),
    ),
    (BillCategory.NURSING, ("nursing",)),
    (BillCategory.MEDICINES, ("pharmacy", "medicine", "drugs")),
    (
        BillCategory.DIAGNOSTICS,
        (
            "lab",
            "laboratory",
            "x-ray",
            "mri",
            "ct scan",
            "ultrasound",
            "investigation",
            "pathology",
            "ecg",
            "radiology",
        ),
    ),
    (
        BillCategory.PROCEDURE,
        ("ot charges", "operation theatre", "procedure", "surgery", "package"),
    ),
]

LINE_RE = re.compile(
    r"^\s*(?P<desc>[A-Za-z][^\n]*?)\s*"
    r"(?:\((?P<days>\d+)\s*days?\s*@\s*(?:INR|Rs\.?)?\s*(?P<rate>[\d,]+(?:\.\d+)?)\))?\s*"
    r"\.{3,}\s*(?:INR|Rs\.?)?\s*(?P<amt>[\d,]+(?:\.\d+)?)\s*$",
    re.MULTILINE,
)
TOTAL_WORDS = ("total", "net payable", "amount due", "advance")


def categorise(description: str) -> BillCategory:
    d = description.lower()
    for cat, kws in CATEGORY_KEYWORDS:
        if any(re.search(rf"\b{re.escape(k)}", d) for k in kws):
            return cat
    return BillCategory.OTHER


def extract_line_items(doc: ClaimDocument) -> tuple[list[BillLineItem], float | None]:
    items: list[BillLineItem] = []
    rate: float | None = None
    for i, m in enumerate(LINE_RE.finditer(doc.text)):
        desc = m.group("desc").strip()
        if any(w in desc.lower() for w in TOTAL_WORDS):
            continue
        cat = categorise(desc)
        days = int(m.group("days")) if m.group("days") else None
        if cat is BillCategory.ROOM and m.group("rate"):
            rate = _money(m.group("rate"))
        items.append(
            BillLineItem(
                line_id=f"{doc.doc_id}-L{i + 1}",
                description=desc,
                category=cat,
                amount=_money(m.group("amt")),
                days=days,
            )
        )
    return items, rate


def _find(spec: FieldSpec, doc: ClaimDocument) -> tuple[object, float] | None:
    for rank, label in enumerate(spec.labels):
        m = re.search(rf"^\s*{re.escape(label)}{SEP}(.+)$", doc.text, re.IGNORECASE | re.MULTILINE)
        if not m:
            continue
        try:
            value = spec.parse(m.group(1))
        except (ValueError, AttributeError, OverflowError):
            return None, 0.3
        conf = 0.97 if rank == 0 else 0.9
        if doc.doc_type not in spec.preferred_docs:
            conf -= 0.1
        return value, conf
    return None


def _pref_rank(spec: FieldSpec, doc: ClaimDocument) -> int:
    prefs = spec.preferred_docs
    return prefs.index(doc.doc_type) if doc.doc_type in prefs else len(prefs)


def extract_facts(documents: list[ClaimDocument]) -> ClaimFacts:
    facts = ClaimFacts()
    for spec in FIELDS:
        candidates: list[tuple[object, float, ClaimDocument]] = []
        for doc in documents:
            hit = _find(spec, doc)
            if hit is not None:
                candidates.append((hit[0], hit[1], doc))
        valid = [c for c in candidates if c[0] is not None]
        if not valid:
            if candidates:  # label found but unparseable
                facts.field_confidence[spec.name] = 0.3
            continue
        distinct = {repr(v) for v, _, _ in valid}
        # Prefer the most authoritative document type for this field, then confidence.
        valid.sort(key=lambda c: (_pref_rank(spec, c[2]), -c[1]))
        value, conf, doc = valid[0]
        if len(distinct) > 1:
            conf = 0.5
            facts.conflicts[spec.name] = sorted({str(v) for v, _, _ in valid})
        setattr(facts, spec.name, value)
        facts.field_confidence[spec.name] = round(conf, 2)
        facts.field_source[spec.name] = doc.doc_id

    for doc in documents:
        if doc.doc_type is DocumentType.INVOICE:
            items, rate = extract_line_items(doc)
            facts.line_items.extend(items)
            if rate is not None and facts.room_rent_per_day is None:
                facts.room_rent_per_day = rate
                facts.field_source["room_rent_per_day"] = doc.doc_id
    if facts.line_items:
        facts.field_confidence["line_items"] = 0.95
    return facts
