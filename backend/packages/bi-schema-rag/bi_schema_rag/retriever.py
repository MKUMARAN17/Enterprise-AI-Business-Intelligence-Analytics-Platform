"""Hybrid retrieval: vector similarity blended with keyword overlap.

This is the "Hybrid (FAISS + Full-Text)" requirement. Pure vector search is
strong on paraphrase ("staff productivity" ~ EMPLOYEE_PERFORMANCE) but can miss
an exact identifier the user typed verbatim ("BRANCH_ID"); pure keyword search
is the opposite. So the retriever computes both a cosine score (from
:class:`~bi_schema_rag.index.SchemaIndex`) and a lexical token-overlap score
(approximating a full-text match), then blends them into a single ranking.

The blend also gives us robustness for the stdlib fallback: the
:class:`~bi_schema_rag.embeddings.HashingEmbedder` is only a coarse lexical
signal, so the explicit keyword boost meaningfully sharpens ranking when no
learned embedding model is available.
"""

from __future__ import annotations

from .embeddings import HashingEmbedder, tokenize
from .errors import EmptyIndexError
from .index import SchemaIndex
from .models import RetrievedChunk

# Blend weight: how much the lexical overlap contributes relative to cosine.
# Cosine carries the primary semantic signal; the keyword boost is a corrective
# nudge, so it is weighted below 1.0. Tuned so that an exact identifier match
# can promote an otherwise mid-ranked table without letting a single shared
# stopword-like token dominate a strong semantic match.
_KEYWORD_WEIGHT = 0.5


class SchemaRetriever:
    """Retrieves the most relevant schema/glossary chunks for a question.

    Holds a reference to a built :class:`SchemaIndex` and re-embeds each query
    with the *same* embedder family the index was built with. Because the
    default is the deterministic :class:`HashingEmbedder`, retrieval is fully
    reproducible without any ML dependency.
    """

    def __init__(self, index: SchemaIndex) -> None:
        if len(index) == 0:
            raise EmptyIndexError("cannot construct a retriever over an empty index")
        self._index = index
        # The query embedder must live in the same vector space as the index.
        # We use a HashingEmbedder sized to the index dimensionality; this is
        # the default index embedder, and its vectors are dimension-compatible
        # for scoring. (A bge-backed index would supply its own query embedder
        # in a future extension; the hashing path is the guaranteed fallback.)
        self._query_embedder = HashingEmbedder(dim=index.dim)

    def retrieve(self, query: str, k: int = 6) -> list[RetrievedChunk]:
        """Return the top-``k`` chunks for ``query``, best first.

        Scoring is ``cosine + _KEYWORD_WEIGHT * keyword_overlap`` where the
        keyword overlap is the fraction of distinct query tokens that appear in
        a document (Jaccard-style recall of the query against the doc text).
        Blending in document order and only *then* sorting keeps ties stable and
        the result deterministic for a given corpus and query.
        """
        if len(self._index) == 0:
            raise EmptyIndexError("cannot retrieve from an empty index")

        k = max(1, k)
        query_vec = self._query_embedder.embed([query])[0]
        cosines = self._index.similarities(query_vec)
        query_tokens = set(tokenize(query))

        chunks: list[RetrievedChunk] = []
        for i, cosine in enumerate(cosines):
            kind, name, text = self._index.document(i)
            boost = self._keyword_overlap(query_tokens, text)
            score = cosine + _KEYWORD_WEIGHT * boost
            chunks.append(RetrievedChunk(kind=kind, name=name, text=text, score=score))

        # Sort by score desc; break ties by name for deterministic output.
        chunks.sort(key=lambda c: (-c.score, c.name))
        return chunks[:k]

    @staticmethod
    def _keyword_overlap(query_tokens: set[str], text: str) -> float:
        """Fraction of distinct query tokens present in ``text`` (0.0–1.0).

        This approximates a full-text match: it rewards documents that literally
        contain the words the user typed (table names, column names, glossary
        phrases). Normalizing by the query-token count keeps the boost bounded
        regardless of document length, so a long table doc cannot win on volume
        alone.
        """
        if not query_tokens:
            return 0.0
        doc_tokens = set(tokenize(text))
        matches = len(query_tokens & doc_tokens)
        return matches / len(query_tokens)

    @staticmethod
    def format_context(chunks: list[RetrievedChunk]) -> str:
        """Render retrieved chunks into a prompt-ready context block.

        The output is grouped and labelled so the SQL-generation agent can see,
        at a glance, which concrete tables and which business definitions were
        judged relevant — and can quote UPPERCASE names straight from the block.
        An empty input yields an explicit "no schema" sentinel rather than an
        empty string, so the agent's prompt never silently loses this section.
        """
        if not chunks:
            return "No relevant schema was retrieved for this question."

        lines: list[str] = ["Relevant schema context:", ""]
        for rank, chunk in enumerate(chunks, start=1):
            header = f"[{rank}] ({chunk.kind}) {chunk.name}  score={chunk.score:.4f}"
            lines.append(header)
            lines.append(chunk.text)
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"
