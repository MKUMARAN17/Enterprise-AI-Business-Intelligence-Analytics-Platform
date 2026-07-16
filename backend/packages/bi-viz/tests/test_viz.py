"""Behavioural tests for :mod:`bi_viz`.

The suite is organised around the decision cascade in
:func:`bi_viz.select_visualization`: one (or more) cases per rule, plus direct
coverage of the type inference and spec builder that the rules stand on. Every
assertion is expressed in terms of observable outputs (chosen ``kind``, chosen
axes, emitted mark/encoding) so the tests document the contract rather than the
implementation. The suite is pure stdlib and needs no chart library.
"""

from __future__ import annotations

import pytest

from bi_viz import (
    Dataset,
    UnknownChartKindError,
    VizChoice,
    VizError,
    build_chart_spec,
    select_visualization,
)

# --------------------------------------------------------------------------- #
# Fixtures / sample datasets
# --------------------------------------------------------------------------- #

MONTHLY_TREND = Dataset(
    columns=("SALE_MONTH", "TOTAL_SALES"),
    rows=(
        ("2024-01-01", 120),
        ("2024-02-01", 150),
        ("2024-03-01", 130),
        ("2024-04-01", 175),
    ),
)

TOP_BRANCHES = Dataset(
    columns=("BRANCH", "TOTAL_SALES"),
    rows=(
        ("North", 120),
        ("South", 90),
        ("East", 200),
        ("West", 60),
    ),
)

TWO_NUMERIC = Dataset(
    columns=("UNITS_SOLD", "REVENUE"),
    rows=(
        (10, 100.0),
        (20, 250.0),
        (30, 330.0),
    ),
)

EMPTY = Dataset(columns=("BRANCH", "TOTAL_SALES"), rows=())

SINGLE_COLUMN = Dataset(columns=("BRANCH",), rows=(("North",), ("South",)))


# --------------------------------------------------------------------------- #
# column_types inference
# --------------------------------------------------------------------------- #


def test_column_types_temporal_by_name():
    # A ``_MONTH`` suffix forces the time axis even though values look date-ish.
    types = MONTHLY_TREND.column_types()
    assert types["SALE_MONTH"] == "temporal"
    assert types["TOTAL_SALES"] == "numeric"


def test_column_types_temporal_by_iso_value():
    ds = Dataset(columns=("CREATED", "N"), rows=(("2024-01-01", 1), ("2024-02-02", 2)))
    assert ds.column_types()["CREATED"] == "temporal"


def test_column_types_categorical_and_numeric():
    types = TOP_BRANCHES.column_types()
    assert types["BRANCH"] == "categorical"
    assert types["TOTAL_SALES"] == "numeric"


def test_column_types_bool_is_not_numeric():
    # Booleans are flags, not measures — they must not read as numeric.
    ds = Dataset(columns=("IS_ACTIVE",), rows=((True,), (False,)))
    assert ds.column_types()["IS_ACTIVE"] == "categorical"


def test_column_types_all_null_is_categorical():
    ds = Dataset(columns=("NOTE",), rows=((None,), (None,)))
    assert ds.column_types()["NOTE"] == "categorical"


def test_row_count_and_is_empty():
    assert MONTHLY_TREND.row_count == 4
    assert not MONTHLY_TREND.is_empty
    assert EMPTY.is_empty
    assert EMPTY.row_count == 0


# --------------------------------------------------------------------------- #
# Rule 1 — table for empty / single column
# --------------------------------------------------------------------------- #


def test_empty_dataset_is_table():
    choice = select_visualization(EMPTY, request_hint="sales trend over time")
    assert choice.kind == "table"
    assert choice.x is None and choice.y is None


def test_single_column_is_table():
    choice = select_visualization(SINGLE_COLUMN, request_hint="top branches")
    assert choice.kind == "table"


# --------------------------------------------------------------------------- #
# Rule 2 — line for monthly trend
# --------------------------------------------------------------------------- #


def test_monthly_trend_is_line():
    choice = select_visualization(MONTHLY_TREND, request_hint="show the monthly sales trend")
    assert choice.kind == "line"
    assert choice.x == "SALE_MONTH"
    assert choice.y == "TOTAL_SALES"


def test_last_n_months_hint_is_line():
    choice = select_visualization(MONTHLY_TREND, request_hint="sales for the last 6 months")
    assert choice.kind == "line"


def test_line_spec_mark_and_encoding():
    choice = select_visualization(MONTHLY_TREND, request_hint="trend over time")
    spec = choice.spec
    assert spec["mark"]["type"] == "line"
    assert spec["encoding"]["x"]["field"] == "SALE_MONTH"
    assert spec["encoding"]["x"]["type"] == "temporal"
    assert spec["encoding"]["y"]["type"] == "quantitative"


# --------------------------------------------------------------------------- #
# Rule 3 — bar for comparison / top-N
# --------------------------------------------------------------------------- #


def test_top_branches_is_bar():
    choice = select_visualization(TOP_BRANCHES, request_hint="top branches by sales")
    assert choice.kind == "bar"
    assert choice.x == "BRANCH"
    assert choice.y == "TOTAL_SALES"


def test_bar_spec_mark_and_encoding():
    choice = select_visualization(TOP_BRANCHES, request_hint="compare branches")
    spec = choice.spec
    assert spec["mark"] == "bar"
    assert spec["encoding"]["x"]["field"] == "BRANCH"
    assert spec["encoding"]["y"]["field"] == "TOTAL_SALES"


def test_bar_top_n_limits_and_sorts_rows():
    choice = select_visualization(TOP_BRANCHES, request_hint="top branches", top_n=2)
    values = choice.spec["data"]["values"]
    assert len(values) == 2
    # East (200) then North (120) are the two highest.
    assert [v["BRANCH"] for v in values] == ["East", "North"]


# --------------------------------------------------------------------------- #
# Rule 4 — pie for proportion / share
# --------------------------------------------------------------------------- #


def test_share_hint_is_pie():
    choice = select_visualization(TOP_BRANCHES, request_hint="sales share by branch")
    assert choice.kind == "pie"
    spec = choice.spec
    assert spec["mark"]["type"] == "arc"
    assert spec["encoding"]["theta"]["field"] == "TOTAL_SALES"
    assert spec["encoding"]["color"]["field"] == "BRANCH"


def test_share_with_many_categories_falls_back_to_bar():
    many = Dataset(
        columns=("CATEGORY", "AMOUNT"),
        rows=tuple((f"C{i}", i) for i in range(20)),
    )
    choice = select_visualization(many, request_hint="distribution of spend by category")
    assert choice.kind == "bar"


# --------------------------------------------------------------------------- #
# Rule 5 — scatter for two numeric columns
# --------------------------------------------------------------------------- #


def test_two_numeric_is_scatter():
    choice = select_visualization(TWO_NUMERIC)
    assert choice.kind == "scatter"
    assert choice.x == "UNITS_SOLD"
    assert choice.y == "REVENUE"
    assert choice.spec["mark"]["type"] == "point"


# --------------------------------------------------------------------------- #
# Rule 6 — table fallback
# --------------------------------------------------------------------------- #


def test_no_matching_heuristic_is_table():
    # Two categorical columns, no numeric/temporal, no useful hint.
    ds = Dataset(columns=("REGION", "MANAGER"), rows=(("N", "Alice"), ("S", "Bob")))
    choice = select_visualization(ds)
    assert choice.kind == "table"


def test_table_spec_carries_data_and_render_tag():
    choice = select_visualization(EMPTY)
    assert choice.spec["data"]["values"] == []
    assert choice.spec["usermeta"]["bi_viz"]["render"] == "table"


# --------------------------------------------------------------------------- #
# build_chart_spec — direct
# --------------------------------------------------------------------------- #


def test_build_chart_spec_inlines_rows_as_dicts():
    spec = build_chart_spec("bar", TOP_BRANCHES, "BRANCH", "TOTAL_SALES", title="Sales")
    assert spec["title"] == "Sales"
    assert spec["data"]["values"][0] == {"BRANCH": "North", "TOTAL_SALES": 120}
    assert spec["$schema"].endswith("v5.json")


def test_build_chart_spec_unknown_kind_raises():
    with pytest.raises(UnknownChartKindError):
        build_chart_spec("heatmap", TOP_BRANCHES, "BRANCH", "TOTAL_SALES")


def test_build_chart_spec_non_table_requires_axes():
    with pytest.raises(VizError):
        build_chart_spec("bar", TOP_BRANCHES, None, None)


def test_unknown_chart_kind_error_is_viz_error():
    # The specific error must be catchable via the package's base error.
    assert issubclass(UnknownChartKindError, VizError)


def test_viz_choice_is_frozen():
    choice = select_visualization(TWO_NUMERIC)
    assert isinstance(choice, VizChoice)
    with pytest.raises(AttributeError):
        choice.kind = "bar"  # type: ignore[misc]
