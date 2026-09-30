from datetime import date

from claimtrace.domain.models import (
    BillCategory,
    BillLineItem,
    ClaimDocument,
    ClaimFacts,
    DocumentType,
)


def docs(*types: DocumentType) -> list[ClaimDocument]:
    types = types or (DocumentType.CLAIM_FORM, DocumentType.DISCHARGE_SUMMARY, DocumentType.INVOICE)
    return [
        ClaimDocument(doc_id=f"D{i}", filename=f"{t}.txt", text="", doc_type=t)
        for i, t in enumerate(types)
    ]


def facts(**overrides) -> ClaimFacts:
    base = dict(
        patient_name="Test Patient",
        patient_age=40,
        policy_start_date=date(2020, 1, 1),
        admission_date=date(2025, 3, 10),
        discharge_date=date(2025, 3, 13),
        diagnosis="Acute appendicitis",
        procedure="Laparoscopic appendectomy",
        line_items=[
            BillLineItem(
                line_id="L1",
                description="Room Rent",
                category=BillCategory.ROOM,
                amount=15000,
                days=3,
            ),
            BillLineItem(
                line_id="L2",
                description="OT Charges",
                category=BillCategory.PROCEDURE,
                amount=30000,
            ),
            BillLineItem(
                line_id="L3",
                description="Surgeon Fee",
                category=BillCategory.SURGEON_FEE,
                amount=20000,
            ),
            BillLineItem(
                line_id="L4", description="Pharmacy", category=BillCategory.MEDICINES, amount=10000
            ),
        ],
    )
    base.update(overrides)
    f = ClaimFacts(**base)
    if f.claimed_amount is None:
        f.claimed_amount = f.bill_total
    return f
