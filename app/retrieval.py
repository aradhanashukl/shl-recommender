"""
TF-IDF retrieval over the SHL catalog.

Why TF-IDF (not embeddings):
- Zero external API latency — retrieval must finish fast inside 30s timeout
- ~370 items is small enough that TF-IDF recall is excellent
- Fully deterministic and debuggable (important for the interview defense)

Gemini is used ONLY for understanding conversation + generating the reply.
It is never in the retrieval hot-path.
"""
import re
from typing import List, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from .catalog import load_catalog


def _doc_text(item: dict) -> str:
    """Build a rich text blob per assessment for TF-IDF indexing.
    Name is repeated 3x to give it higher weight in TF-IDF scoring.
    """
    name = item.get("name") or ""
    parts = [
        name, name, name,          # weight name strongly
        item.get("description") or "",
        " ".join(item.get("test_type_names") or []),
        " ".join(item.get("job_levels") or []),
        item.get("duration") or "",
    ]
    return " ".join(p for p in parts if p)


def _report_penalty(name: str) -> float:
    """
    FIX 2: Penalise derivative report variants so base assessments rank higher.
    e.g. 'OPQ Leadership Report' should rank below 'Occupational Personality
    Questionnaire OPQ32r' when the user asks about a senior role.

    Pure report = has 'report' in the name but is NOT itself a questionnaire,
    instrument, scenarios, simulation, or interactive test.
    """
    n = name.lower()
    if not re.search(r'\breport\b', n):
        return 1.0                          # not a report — no penalty
    if re.search(r'\b(questionnaire|instrument|scenarios|simulation|interactive|verify|automata|writeX)\b', n):
        return 1.0                          # it's a report WITH its own content
    return 0.6                              # pure report variant — penalise


class CatalogIndex:
    def __init__(self):
        self.items = load_catalog()
        self._texts = [_doc_text(it) for it in self.items]
        self.vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            min_df=1,
        )
        self.matrix = self.vectorizer.fit_transform(self._texts)

    def search(self, query: str, top_k: int = 15) -> List[Tuple[dict, float]]:
        if not query.strip():
            return []
        q_vec = self.vectorizer.transform([query])
        sims = cosine_similarity(q_vec, self.matrix)[0]

        # Apply report penalty before ranking
        penalised = [
            (item, score * _report_penalty(item["name"]))
            for item, score in zip(self.items, sims)
        ]
        ranked = sorted(penalised, key=lambda x: x[1], reverse=True)
        return [(it, score) for it, score in ranked[:top_k] if score > 0]

    def find_by_name(self, name: str) -> dict | None:
        """Exact match first, then substring — used to validate Gemini's choices."""
        name_low = name.lower().strip()
        for it in self.items:
            if it["name"].lower().strip() == name_low:
                return it
        for it in self.items:
            if name_low in it["name"].lower():
                return it
        return None

    def get_all_names(self) -> List[str]:
        return [it["name"] for it in self.items]


_INDEX: CatalogIndex | None = None


def get_index() -> CatalogIndex:
    global _INDEX
    if _INDEX is None:
        _INDEX = CatalogIndex()
    return _INDEX