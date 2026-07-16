# bi-viz

Automatic visualization selection for the enterprise AI BI platform.

`bi_viz` turns a query result into the chart that communicates it best. It looks
at the *shape* of the result (how many columns, of what inferred type) and a
light-weight hint about the user's intent, then returns a ready-to-render
Vega-Lite v5 spec.

## Why

A natural-language BI answer comes back as a table of numbers. A bare table is
almost always a poor default: a monthly trend wants a line, a "top branches"
ranking wants a bar, a share breakdown wants a pie. This package encodes that
editorial judgement as a small, deterministic, explainable rule cascade so every
answer is charted consistently — and every choice carries a human-readable
`reason`.

## Runtime dependencies

None. `bi_viz` emits JSON-serialisable Vega-Lite spec dictionaries and leaves
rendering to the frontend, so it is pure standard library.

## Usage

```python
from bi_viz import Dataset, select_visualization

ds = Dataset(
    columns=("SALE_MONTH", "TOTAL_SALES"),
    rows=(("2024-01-01", 120), ("2024-02-01", 150), ("2024-03-01", 130)),
)
choice = select_visualization(ds, request_hint="sales trend over time")

choice.kind    # "line"
choice.x       # "SALE_MONTH"
choice.y       # "TOTAL_SALES"
choice.reason  # "line: trend intent with temporal column ..."
choice.spec    # a complete Vega-Lite v5 spec dict
```

## Decision cascade

1. Empty result or a single column -> `table`.
2. Trend intent (`trend`, `over time`, `monthly`, `last N months`, ...) plus a
   temporal column -> `line`.
3. Compare/top/rank intent with one categorical + one numeric column -> `bar`
   (optionally truncated to `top_n`).
4. Proportion/share intent with one categorical + one numeric column and
   <= ~12 categories -> `pie` (more categories fall back to `bar`).
5. Two numeric columns and no temporal column -> `scatter`.
6. Otherwise -> `table`.

## Development

```bash
pytest
```

Tests run stdlib-only.
