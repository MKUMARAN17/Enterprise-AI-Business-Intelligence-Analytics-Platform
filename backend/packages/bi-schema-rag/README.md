# bi-schema-rag

Schema-aware Retrieval-Augmented Generation for the enterprise BI platform's
SQL-generation agent.

Given a natural-language question, this package retrieves only the relevant
slice of the MySQL schema (tables, columns, foreign keys) plus matching
business-glossary terms, and renders them into a prompt-ready context block.
That keeps the SQL agent's prompt small and grounded, so it quotes real
UPPERCASE table/column names and joins on real foreign keys instead of guessing.

## Runs stdlib-only

The package works with **pure standard library**. FAISS + `BAAI/bge-small-en-v1.5`
embeddings are an *optional* acceleration, imported lazily. When they are not
installed, the package falls back to:

- a deterministic bag-of-words **hashing embedder** (`HashingEmbedder`), and
- a **hybrid retriever** blending cosine similarity with keyword (full-text-style)
  overlap.

Install the optional acceleration with:

```
pip install "bi-schema-rag[faiss]"
```

## Usage

```python
from bi_schema_rag import SchemaIndex, SchemaRetriever, default_catalog

tables, glossary = default_catalog()
index = SchemaIndex.build(tables, glossary)          # defaults to HashingEmbedder
retriever = SchemaRetriever(index)

chunks = retriever.retrieve("collection performance by branch", k=6)
context = SchemaRetriever.format_context(chunks)
print(context)   # drop straight into the SQL agent's prompt
```

## Public API

- `models`: `ColumnDoc`, `TableDoc`, `GlossaryDoc`, `RetrievedChunk`
- `embeddings`: `Embedder`, `HashingEmbedder`, `try_load_bge_embedder`
- `index`: `SchemaIndex.build(tables, glossary, embedder=None)`
- `retriever`: `SchemaRetriever.retrieve(query, k=6)`, `SchemaRetriever.format_context(chunks)`
- `catalog`: `default_catalog()`
- `errors`: `SchemaRagError`, `EmptyIndexError`

## Tests

```
pytest
```

Tests pass without faiss/torch/sentence-transformers installed.
