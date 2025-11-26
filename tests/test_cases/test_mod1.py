import pytest
from warnings import warn


def test_sum():
    warn("warning")
    assert 1 + 1 == 2


# @pytest.mark.xfail
def test_fail():
    assert 1 + 1 == 3


def test_dict_fail():
    assert {} == {"test_key": "test_value"}


@pytest.mark.custom1
def test_mark_custom():
    assert True


@pytest.mark.custom
@pytest.mark.custom_two
def test_mark_custom_two():
    assert True


@pytest.mark.skip
def test_mark_skip():
    assert 1 + 1 == 3


@pytest.mark.parametrize(
    "a, b, result",
    [
        (1, 1, 2),
        (1, 2, 3),
    ],
)
def test_mark(a, b, result):
    assert a + b == result


@pytest.mark.parametrize(
    "sequence",
    ["red", "*", "[+]", "[]", "/"],
)
def test_weird_fixtures(sequence):
    assert True
