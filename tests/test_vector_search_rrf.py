"""Tests para VectorSearchService._fuse_rrf() — fusión Reciprocal Rank Fusion."""
import pytest
from uuid import uuid4

from app.core.services.vector_search_service import VectorSearchService, _RRF_K


def _make_result(chunk_id=None, score=0.9, content="test"):
    """Helper para crear un resultado de búsqueda ficticio."""
    return {
        "chunk_id": chunk_id or str(uuid4()),
        "document_id": str(uuid4()),
        "content": content,
        "metadata": "{}",
        "source_page": 1,
        "source_row": None,
        "filename": "test.pdf",
        "score": score,
    }


class TestFuseRRF:
    """Tests para _fuse_rrf (lógica pura, no usa self)."""

    def test_chunk_in_both_lists_scores_higher(self, vector_search):
        shared_id = str(uuid4())
        only_vector_id = str(uuid4())

        vector = [
            _make_result(chunk_id=shared_id),
            _make_result(chunk_id=only_vector_id),
        ]
        fts = [
            _make_result(chunk_id=shared_id),
        ]

        results = vector_search._fuse_rrf(vector, fts, max_results=10)

        scores = {r["chunk_id"]: r["score"] for r in results}
        assert scores[shared_id] > scores[only_vector_id]

    def test_rank1_in_both_lists_is_max_score(self, vector_search):
        cid = str(uuid4())
        vector = [_make_result(chunk_id=cid)]
        fts = [_make_result(chunk_id=cid)]

        results = vector_search._fuse_rrf(vector, fts, max_results=10)

        # rank 1 en ambas listas → score teórico = 2/(k+1) / (2/(k+1)) = 1.0
        assert len(results) == 1
        assert abs(results[0]["score"] - 1.0) < 1e-9

    def test_rank1_in_one_list_scores_half(self, vector_search):
        cid = str(uuid4())
        vector = [_make_result(chunk_id=cid)]
        fts = []  # Sin resultados FTS

        # Con FTS vacío, _fuse_rrf no se llama normalmente,
        # pero forzamos la llamada directamente
        results = vector_search._fuse_rrf(vector, [], max_results=10)

        # Solo en una lista → score = 1/(k+1) / (2/(k+1)) = 0.5
        assert len(results) == 1
        assert abs(results[0]["score"] - 0.5) < 1e-9

    def test_max_results_respected(self, vector_search):
        vector = [_make_result() for _ in range(10)]
        fts = [_make_result() for _ in range(10)]

        results = vector_search._fuse_rrf(vector, fts, max_results=3)
        assert len(results) <= 3

    def test_results_sorted_descending(self, vector_search):
        ids = [str(uuid4()) for _ in range(5)]
        vector = [_make_result(chunk_id=ids[i]) for i in range(5)]
        fts = [_make_result(chunk_id=ids[4 - i]) for i in range(5)]  # Orden invertido

        results = vector_search._fuse_rrf(vector, fts, max_results=10)

        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_empty_both_lists(self, vector_search):
        results = vector_search._fuse_rrf([], [], max_results=10)
        assert results == []

    def test_deduplication(self, vector_search):
        shared_id = str(uuid4())
        vector = [_make_result(chunk_id=shared_id, content="from_vector")]
        fts = [_make_result(chunk_id=shared_id, content="from_fts")]

        results = vector_search._fuse_rrf(vector, fts, max_results=10)

        # Mismo chunk_id no debería duplicarse
        assert len(results) == 1

    def test_chunk_data_preserved(self, vector_search):
        cid = str(uuid4())
        vector = [_make_result(chunk_id=cid, content="mi contenido")]
        fts = []

        results = vector_search._fuse_rrf(vector, fts, max_results=10)

        assert results[0]["chunk_id"] == cid
        assert results[0]["content"] == "mi contenido"
        assert results[0]["filename"] == "test.pdf"
