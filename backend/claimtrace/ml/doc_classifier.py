"""Document classifiers behind one interface: classify(text) -> (type, confidence)."""

from __future__ import annotations

from functools import lru_cache
from typing import Protocol

from claimtrace.domain.models import DocumentType
from claimtrace.extraction.classifier import classify as keyword_classify


class DocClassifier(Protocol):
    name: str

    def classify(self, text: str) -> tuple[DocumentType, float]: ...


class KeywordDocClassifier:
    """Hand-written keyword signals (v0.1). Fast and explainable; brittle when a document's
    title or signature phrases are missing."""

    name = "keyword"

    def classify(self, text: str) -> tuple[DocumentType, float]:
        return keyword_classify(text)


class TfidfDocClassifier:
    """TF-IDF (word 1-2 grams) + multinomial logistic regression, trained on synthetic
    documents including degraded copies (headers lost, lines dropped)."""

    name = "tfidf_logreg"
    min_confidence = 0.4

    def __init__(self, n_claims: int = 120):
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline

        from claimtrace.ml.data import TRAIN_SEED, labelled_documents, normalise

        pairs = labelled_documents(n_claims, TRAIN_SEED)
        self.model = make_pipeline(
            TfidfVectorizer(
                preprocessor=normalise, ngram_range=(1, 2), sublinear_tf=True, min_df=2
            ),
            LogisticRegression(max_iter=2000, C=5.0),
        )
        self.model.fit([t for t, _ in pairs], [label.value for _, label in pairs])
        self.n_train = len(pairs)

    def classify(self, text: str) -> tuple[DocumentType, float]:
        if not text.strip():
            return DocumentType.UNKNOWN, 0.0
        proba = self.model.predict_proba([text])[0]
        best = int(proba.argmax())
        conf = float(proba[best])
        if conf < self.min_confidence:
            return DocumentType.UNKNOWN, round(conf, 2)
        return DocumentType(self.model.classes_[best]), round(conf, 2)


DOC_CLASSIFIERS = {
    "keyword": ("Keyword rules", "Hand-written signal phrases per document type."),
    "tfidf_logreg": (
        "TF-IDF + logistic regression",
        "Small scikit-learn model trained on synthetic documents, robust to missing headers.",
    ),
}


@lru_cache
def get_doc_classifier(name: str = "keyword") -> DocClassifier:
    if name == "keyword":
        return KeywordDocClassifier()
    if name == "tfidf_logreg":
        return TfidfDocClassifier()
    raise ValueError(f"Unknown document classifier '{name}'")
