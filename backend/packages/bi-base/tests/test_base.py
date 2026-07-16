from __future__ import annotations

import pytest

from bi_base import (
    BiError,
    SqlSafetyError,
    bind_request,
    extract_json,
    get_request_id,
    require_keys,
    stopwatch,
)
from bi_base.structured import StructuredOutputError


def test_extract_json_bare():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_fenced():
    assert extract_json('here you go:\n```json\n{"a": 2}\n```') == {"a": 2}


def test_extract_json_embedded_prose():
    assert extract_json('The answer is {"x": 3} ok') == {"x": 3}


def test_extract_json_empty_raises():
    with pytest.raises(StructuredOutputError):
        extract_json("")


def test_require_keys_ok_and_missing():
    require_keys({"a": 1, "b": 2}, ["a", "b"])
    with pytest.raises(StructuredOutputError):
        require_keys({"a": 1}, ["a", "b"])


def test_error_to_problem_shape():
    err = SqlSafetyError("bad sql")
    p = err.to_problem()
    assert p["code"] == "SQL_UNSAFE"
    assert p["status"] == 400
    assert isinstance(err, BiError)


def test_request_context_roundtrip():
    rid = bind_request(user_id="u1")
    assert get_request_id() == rid


def test_stopwatch_measures():
    with stopwatch() as e:
        sum(range(1000))
    assert e.ms >= 0.0
