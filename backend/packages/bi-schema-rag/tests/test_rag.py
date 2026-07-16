"""Behavioural tests for :mod:`bi_schema_rag`.

These tests deliberately exercise the *pure-stdlib* path only: they never import
faiss, torch, or sentence-transformers, so they run identically in CI without
the optional ML stack. The retrieval assertions check ranking behaviour ("is the
right table in the top results") rather than exact scores, because scores are an
internal, unnormalized ranking signal.
"""

from __future__ import annotations

import math

import pytest

from bi_schema_rag import (
    ColumnDoc,
    EmptyIndexError,
    GlossaryDoc,
    HashingEmbedder,
    RetrievedChunk,
    SchemaIndex,
    SchemaRetriever,
    TableDoc,
    default_catalog,
)


@pytest.fixture
def catalog() -> tuple[list[TableDoc], list[GlossaryDoc]]:
    return default_catalog()


@pytest.fixture
def retriever(catalog) -> SchemaRetriever:
    tables, glossary = catalog
    return SchemaRetriever(SchemaIndex.build(tables, glossary))


def _names(chunks: list[RetrievedChunk]) -> list[str]:
    return [c.name for c in chunks]


# --- HashingEmbedder -------------------------------------------------------


def test_hashing_embedder_is_deterministic() -> None:
    a = HashingEmbedder(dim=64)
    b = HashingEmbedder(dim=64)
    v1 = a.embed(["collection performance by branch"])[0]
    v2 = b.embed(["collection performance by branch"])[0]
    assert v1 == v2


def test_hashing_embedder_vectors_are_l2_normalized() -> None:
    emb = HashingEmbedder(dim=128)
    vec = emb.embed(["revenue trend across every branch"])[0]
    norm = math.sqrt(sum(x * x for x in vec))
    assert norm == pytest.approx(1.0, abs=1e-9)


def test_hashing_embedder_dim_is_respected() -> None:
    emb = HashingEmbedder(dim=32)
    vectors = emb.embed(["a", "b c"])
    assert len(vectors) == 2
    assert all(len(v) == 32 for v in vectors)


def test_hashing_embedder_empty_text_is_zero_vector() -> None:
    emb = HashingEmbedder(dim=16)
    vec = emb.embed([""])[0]
    assert vec == [0.0] * 16


def test_hashing_embedder_rejects_bad_dim() -> None:
    with pytest.raises(ValueError):
        HashingEmbedder(dim=0)


def test_different_text_gives_different_vectors() -> None:
    emb = HashingEmbedder(dim=256)
    v1 = emb.embed(["inventory stock levels"])[0]
    v2 = emb.embed(["employee performance comparison"])[0]
    assert v1 != v2


# --- SchemaIndex -----------------------------------------------------------


def test_build_index_from_default_catalog(catalog) -> None:
    tables, glossary = catalog
    index = SchemaIndex.build(tables, glossary)
    assert len(index) == len(tables) + len(glossary)
    assert index.dim == HashingEmbedder().dim


def test_build_empty_corpus_raises() -> None:
    with pytest.raises(EmptyIndexError):
        SchemaIndex.build([], [])


def test_index_document_accessor_roundtrips(catalog) -> None:
    tables, glossary = catalog
    index = SchemaIndex.build(tables, glossary)
    kinds = {index.document(i)[0] for i in range(len(index))}
    assert kinds == {"table", "glossary"}


def test_default_catalog_shape() -> None:
    tables, glossary = default_catalog()
    assert len(tables) >= 8
    assert len(glossary) >= 6
    assert all(t.name.isupper() for t in tables)


# --- SchemaRetriever -------------------------------------------------------


def test_retrieve_collection_performance_by_branch(retriever) -> None:
    chunks = retriever.retrieve("collection performance by branch", k=6)
    names = _names(chunks)
    assert "COLLECTIONS" in names
    assert "BRANCHES" in names


def test_retrieve_employee_performance_comparison(retriever) -> None:
    chunks = retriever.retrieve("employee performance comparison", k=6)
    names = _names(chunks)
    assert "EMPLOYEE_PERFORMANCE" in names or "EMPLOYEES" in names
    # The most specific fact table should rank in the top results.
    assert "EMPLOYEE_PERFORMANCE" in names


def test_retrieve_self_pay_hits_payments(retriever) -> None:
    chunks = retriever.retrieve("how much revenue came from self-pay customers", k=6)
    names = _names(chunks)
    assert "PAYMENTS" in names


def test_glossary_terms_are_retrievable(retriever) -> None:
    chunks = retriever.retrieve("what does collection performance mean", k=6)
    glossary_names = [c.name for c in chunks if c.kind == "glossary"]
    assert "collection performance" in glossary_names


def test_retrieve_respects_k(retriever) -> None:
    for k in (1, 3, 5, 8):
        assert len(retriever.retrieve("revenue trend", k=k)) == k


def test_retrieve_sorted_by_score_desc(retriever) -> None:
    chunks = retriever.retrieve("inventory stock-out risk by branch", k=6)
    scores = [c.score for c in chunks]
    assert scores == sorted(scores, reverse=True)


def test_retrieve_is_deterministic(retriever) -> None:
    q = "underperforming branch revenue"
    assert _names(retriever.retrieve(q, k=6)) == _names(retriever.retrieve(q, k=6))


def test_keyword_boost_promotes_exact_identifier(retriever) -> None:
    # A verbatim column identifier should surface its owning table.
    chunks = retriever.retrieve("QUANTITY_ON_HAND REORDER_LEVEL", k=4)
    assert "INVENTORY" in _names(chunks)


# --- format_context --------------------------------------------------------


def test_format_context_non_empty(retriever) -> None:
    chunks = retriever.retrieve("collection performance by branch", k=4)
    ctx = SchemaRetriever.format_context(chunks)
    assert ctx.strip()
    assert "COLLECTIONS" in ctx
    assert "(table)" in ctx or "(glossary)" in ctx


def test_format_context_empty_input_has_sentinel() -> None:
    ctx = SchemaRetriever.format_context([])
    assert ctx.strip()
    assert "No relevant schema" in ctx


# --- error paths -----------------------------------------------------------


def test_retriever_rejects_empty_index() -> None:
    # Build a valid index, then simulate emptiness via a hand-built instance.
    empty = SchemaIndex(
        _kinds=[], _names=[], _texts=[], _vectors=[], _dim=8, _faiss=None
    )
    with pytest.raises(EmptyIndexError):
        SchemaRetriever(empty)


def test_similarities_on_empty_index_raises() -> None:
    empty = SchemaIndex(
        _kinds=[], _names=[], _texts=[], _vectors=[], _dim=8, _faiss=None
    )
    with pytest.raises(EmptyIndexError):
        empty.similarities([0.0] * 8)


def test_to_document_contains_key_fields() -> None:
    table = TableDoc(
        name="DEMO",
        description="A demo table.",
        columns=(ColumnDoc("DEMO_ID", "INT", "pk"),),
        relationships=("DEMO.X -> OTHER.X",),
        business_terms=("demo term",),
    )
    doc = table.to_document()
    assert "DEMO" in doc
    assert "DEMO_ID" in doc
    assert "DEMO.X -> OTHER.X" in doc
    assert "demo term" in doc
