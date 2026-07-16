"""Immutable data shapes describing the schema/glossary corpus and results.

These dataclasses are the *documents* the retriever indexes and returns. They
are ``frozen`` and ``slots`` for two reasons: (1) documents are treated as
value objects that get hashed into vectors and cached, so accidental mutation
after indexing would silently desync the vectors from their source text; and
(2) ``slots`` keeps per-document memory low when a large enterprise catalog
(hundreds of tables) is held in memory.

The ``to_document`` methods are the single source of truth for *what text gets
embedded*. Keeping the rendering on the model (rather than in the indexer)
guarantees that the exact same string is used at index time and any time we
need to re-embed or debug a retrieval, and it lets the SQL agent's prompt show
the user a human-readable version of what was matched.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ColumnDoc:
    """A single MySQL column's metadata.

    ``data_type`` mirrors the MySQL declaration (e.g. ``DECIMAL(12,2)``,
    ``VARCHAR(64)``) so the SQL agent can reason about casts and aggregations;
    ``description`` carries the business meaning that a bare column name cannot.
    """

    name: str
    data_type: str
    description: str


@dataclass(frozen=True, slots=True)
class TableDoc:
    """A MySQL table with its columns, foreign keys, and business synonyms.

    ``name`` is UPPERCASE to match the platform's MySQL naming convention so the
    retrieved text can be pasted verbatim into generated SQL. ``relationships``
    are rendered foreign-key edges (``"COLLECTIONS.BRANCH_ID -> BRANCHES.BRANCH_ID"``)
    that let the agent join correctly, and ``business_terms`` are natural-language
    synonyms ("collection performance") that bridge the vocabulary gap between how
    users ask questions and how columns are named.
    """

    name: str
    description: str
    columns: tuple[ColumnDoc, ...]
    relationships: tuple[str, ...]
    business_terms: tuple[str, ...]

    def to_document(self) -> str:
        """Render a compact, embed-ready text block for this table.

        The layout deliberately front-loads the table name and description
        (the strongest retrieval signal) and folds column names, foreign keys,
        and business synonyms into the same blob so a keyword match on *any* of
        them contributes to the hybrid score. This is the exact string that is
        embedded and full-text scored.
        """
        columns = ", ".join(f"{c.name} {c.data_type} ({c.description})" for c in self.columns)
        parts = [
            f"TABLE {self.name}: {self.description}",
            f"Columns: {columns}",
        ]
        if self.relationships:
            parts.append("Foreign keys: " + "; ".join(self.relationships))
        if self.business_terms:
            parts.append("Business terms: " + ", ".join(self.business_terms))
        return "\n".join(parts)


@dataclass(frozen=True, slots=True)
class GlossaryDoc:
    """A business glossary entry linking domain language to concrete tables.

    Users ask for "underperforming branches" or "self-pay", not for
    ``BRANCHES`` joined to ``REVENUE``. Glossary docs are first-class corpus
    members so those phrases retrieve directly, and ``related_tables`` tells the
    SQL agent which tables to pull once the concept matches.
    """

    term: str
    definition: str
    related_tables: tuple[str, ...]

    def to_document(self) -> str:
        """Render an embed-ready text block for this glossary term."""
        parts = [f"GLOSSARY {self.term}: {self.definition}"]
        if self.related_tables:
            parts.append("Related tables: " + ", ".join(self.related_tables))
        return "\n".join(parts)


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    """One scored search result handed back to the SQL-generation agent.

    ``kind`` is ``"table"`` or ``"glossary"`` so the caller can weight or format
    the two differently; ``text`` is the rendered ``to_document`` output ready to
    drop into a prompt; ``score`` is the blended hybrid score (higher is better)
    used purely for ranking and is not otherwise normalized across queries.
    """

    kind: str
    name: str
    text: str
    score: float
