import random

from claimtrace.domain.models import BillCategory, DocumentType
from claimtrace.evaluation.synthetic import Scenario, generate_claim
from claimtrace.extraction.classifier import classify
from claimtrace.extraction.extractor import categorise
from claimtrace.extraction.pipeline import extract, ingest_documents
from claimtrace.policies.registry import get_policy


def _claim(scenario=Scenario.CLEAN, seed=1):
    return generate_claim(random.Random(seed), 1, scenario, get_policy("SURAKSHA-SILVER"))


def test_documents_are_classified():
    docs = ingest_documents(_claim().documents)
    assert [d.doc_type for d in docs] == [
        DocumentType.CLAIM_FORM,
        DocumentType.DISCHARGE_SUMMARY,
        DocumentType.INVOICE,
    ]


def test_unknown_document():
    assert classify("hello world")[0] is DocumentType.UNKNOWN


def test_fields_extracted_match_ground_truth():
    sc = _claim()
    f = extract(ingest_documents(sc.documents))
    tf = sc.truth_facts
    assert f.patient_name == tf.patient_name
    assert f.admission_date == tf.admission_date
    assert f.discharge_date == tf.discharge_date
    assert f.policy_start_date == tf.policy_start_date
    assert f.diagnosis == tf.diagnosis
    assert f.claimed_amount == tf.claimed_amount
    assert f.bill_total == tf.claimed_amount
    assert len(f.line_items) == len(tf.lines)
    assert all(f.field_source.get(k) for k in ("diagnosis", "admission_date"))


def test_conflicting_values_are_recorded_not_silently_resolved():
    f = extract(ingest_documents(_claim(Scenario.CONFLICTING_DATES).documents))
    assert "admission_date" in f.conflicts
    assert f.field_confidence["admission_date"] == 0.5


def test_categorise():
    assert categorise("Surgical Consumables") is BillCategory.CONSUMABLES
    assert categorise("Room Rent - Deluxe") is BillCategory.ROOM
    assert categorise("Intraocular lens implant") is BillCategory.IMPLANTS
    assert categorise("Laboratory Investigations") is BillCategory.DIAGNOSTICS
