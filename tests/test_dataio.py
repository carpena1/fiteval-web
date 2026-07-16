import numpy as np
import pytest

from fiteval_core.dataio import (DataError, drop_nan_rows, drop_repeated_rows,
                                 parse_numeric_text, read_in_file, swap_first_two,
                                 write_in_file)


def test_parse_whitespace_and_blank_lines():
    arr = parse_numeric_text("1 2\n\n3\t4\n 5  6 \n")
    assert arr.shape == (3, 2)
    np.testing.assert_array_equal(arr, [[1, 2], [3, 4], [5, 6]])


def test_parse_rejects_ragged():
    with pytest.raises(DataError):
        parse_numeric_text("1 2\n3 4 5\n")


def test_parse_rejects_text():
    with pytest.raises(DataError):
        parse_numeric_text("a b\n")


def test_file_round_trip(tmp_path):
    data = np.array([[1.5, 2.25], [3.0, 4.125]])
    p = tmp_path / "test.in"
    write_in_file(data, p)
    np.testing.assert_allclose(read_in_file(p), data)


def test_swap_first_two():
    arr = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    swapped = swap_first_two(arr)
    np.testing.assert_array_equal(swapped, [[2, 1, 3], [5, 4, 6]])
    np.testing.assert_array_equal(swap_first_two(swapped), arr)  # involution


def test_drop_nan_rows():
    yobs = np.array([1.0, np.nan, 3.0])
    yprd = np.array([1.0, 2.0, np.nan])
    (o, p), removed = drop_nan_rows(yobs, yprd)
    np.testing.assert_array_equal(o, [1.0])
    assert removed == 2


def test_drop_repeated_rows():
    data = np.array([[1.0, 2.0], [3.0, 4.0], [1.0, 2.0], [5.0, 6.0]])
    out, removed = drop_repeated_rows(data)
    assert removed == 1
    assert out.shape == (3, 2)
    # duplicated row moved to front (MATLAB TEMP=[DATA(i,:); ...] behavior)
    np.testing.assert_array_equal(out[0], [1.0, 2.0])
    np.testing.assert_array_equal(out[1], [3.0, 4.0])
    np.testing.assert_array_equal(out[2], [5.0, 6.0])


def test_drop_repeated_no_repeats_keeps_order():
    data = np.array([[1.0, 2.0], [3.0, 4.0]])
    out, removed = drop_repeated_rows(data)
    assert removed == 0
    np.testing.assert_array_equal(out, data)
