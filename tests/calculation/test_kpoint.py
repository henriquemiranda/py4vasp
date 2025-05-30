# Copyright © VASP Software GmbH,
# Licensed under the Apache License 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
import types

import numpy as np
import pytest

from py4vasp import exception
from py4vasp._calculation.kpoint import Kpoint


@pytest.fixture
def explicit_kpoints(raw_data):
    raw_kpoints = raw_data.kpoint("explicit with_labels")
    kpoints = Kpoint.from_data(raw_kpoints)
    kpoints.ref = types.SimpleNamespace()
    kpoints.ref.mode = "explicit"
    kpoints.ref.line_length = len(raw_kpoints.coordinates)
    kpoints.ref.coordinates = raw_kpoints.coordinates
    kpoints.ref.weights = raw_kpoints.weights
    kpoints.ref.labels = [""] * len(raw_kpoints.coordinates)
    # note index difference between Fortran and Python
    kpoints.ref.labels[8] = "foo"
    kpoints.ref.labels[24] = "bar"
    kpoints.ref.labels[39] = "baz"
    cartesian = to_cartesian(raw_kpoints.coordinates, raw_kpoints.cell)
    kpoints.ref.distances = line_distances(cartesian)
    return kpoints


@pytest.fixture
def grid_kpoints(raw_data):
    raw_kpoints = raw_data.kpoint("automatic")
    kpoints = Kpoint.from_data(raw_kpoints)
    kpoints.ref = types.SimpleNamespace()
    kpoints.ref.line_length = len(raw_kpoints.coordinates)
    return kpoints


@pytest.fixture
def line_kpoints(raw_data):
    raw_kpoints = raw_data.kpoint("line with_labels")
    kpoints = Kpoint.from_data(raw_kpoints)
    kpoints.ref = types.SimpleNamespace()
    kpoints.ref.line_length = raw_kpoints.number
    kpoints.ref.number_lines = len(raw_kpoints.coordinates) // raw_kpoints.number
    kpoints.ref.labels = [""] * len(raw_kpoints.coordinates)
    kpoints.ref.labels[0] = r"$\Gamma$"
    kpoints.ref.labels[9] = "M"
    kpoints.ref.labels[10] = r"$\Gamma$"
    kpoints.ref.labels[15] = "Y"
    kpoints.ref.labels[19] = "M"
    cartesian = to_cartesian(raw_kpoints.coordinates, raw_kpoints.cell)
    kpoints.ref.distances = multiple_line_distances(cartesian, kpoints.ref.line_length)
    return kpoints


@pytest.fixture
def qpoints(raw_data):
    raw_kpoints = raw_data.kpoint("qpoints")
    kpoints = Kpoint.from_data(raw_kpoints)
    kpoints.ref = types.SimpleNamespace()
    cartesian = to_cartesian(raw_kpoints.coordinates, raw_kpoints.cell)
    kpoints.ref.distances = multiple_line_distances(cartesian, raw_kpoints.number)
    return kpoints


def to_cartesian(direct_coordinates, cell):
    if cell.lattice_vectors.ndim == 2:
        lattice_vectors = cell.lattice_vectors
    else:
        lattice_vectors = cell.lattice_vectors[-1]
    direct_to_cartesian = np.linalg.inv(lattice_vectors)
    return direct_coordinates @ direct_to_cartesian.T


def multiple_line_distances(cartesian, line_length):
    distances = np.zeros(len(cartesian))
    previous = 0
    for i in range(0, len(distances), line_length):
        slice_ = slice(i, i + line_length)
        distances[slice_] = previous + line_distances(cartesian[slice_])
        previous = distances[i + line_length - 1]
    return distances


def line_distances(cartesian):
    distances = np.zeros(len(cartesian))
    distances[1:] = np.cumsum(np.linalg.norm(cartesian[1:] - cartesian[:-1], axis=1))
    return distances


def test_read(explicit_kpoints, Assert):
    actual = explicit_kpoints.read()
    assert actual["mode"] == explicit_kpoints.ref.mode
    assert actual["line_length"] == explicit_kpoints.ref.line_length
    Assert.allclose(actual["coordinates"], explicit_kpoints.ref.coordinates)
    Assert.allclose(actual["weights"], explicit_kpoints.ref.weights)
    assert actual["labels"] == explicit_kpoints.ref.labels


def test_no_labels_read(grid_kpoints):
    assert "labels" not in grid_kpoints.read()


def test_mode(raw_data):
    allowed_mode_formats = {
        "automatic": ["a", b"A", "auto"],
        "generating lattice": ["b", b"B"],
        "explicit": ["e", b"e", "explicit", "ExplIcIT"],
        "gamma": ["g", b"G", "gamma"],
        "line": ["l", b"l", "line"],
        "monkhorst": ["m", b"M", "  Monkhorst-Pack  "],
    }
    for ref_mode, formats in allowed_mode_formats.items():
        for format in formats:
            raw_kpoints = raw_data.kpoint(format)
            actual_mode = Kpoint.from_data(raw_kpoints).mode()
            assert actual_mode == ref_mode
    for unknown_mode in ["x", "y", "z"]:
        with pytest.raises(exception.RefinementError):
            raw_kpoints = raw_data.kpoint(unknown_mode)
            Kpoint.from_data(raw_kpoints).mode()


def test_explicit_kpoints_number_kpoints(explicit_kpoints):
    assert explicit_kpoints.number_kpoints() == explicit_kpoints.ref.line_length


def test_grid_kpoints_number_kpoints(grid_kpoints):
    assert grid_kpoints.number_kpoints() == grid_kpoints.ref.line_length


def test_line_kpoints_number_kpoints(line_kpoints):
    assert line_kpoints.number_kpoints() == len(line_kpoints.ref.distances)


def test_explicit_kpoints_line_length(explicit_kpoints):
    assert explicit_kpoints.line_length() == explicit_kpoints.ref.line_length


def test_grid_kpoints_line_length(grid_kpoints):
    assert grid_kpoints.line_length() == grid_kpoints.ref.line_length


def test_line_kpoints_line_length(line_kpoints):
    assert line_kpoints.line_length() == line_kpoints.ref.line_length


def test_explicit_kpoints_number_lines(explicit_kpoints):
    assert explicit_kpoints.number_lines() == 1


def test_line_kpoints_number_lines(line_kpoints):
    assert line_kpoints.number_lines() == line_kpoints.ref.number_lines


def test_explicit_kpoints_labels(explicit_kpoints):
    assert explicit_kpoints.labels() == explicit_kpoints.ref.labels


def test_line_kpoints_labels(line_kpoints):
    assert line_kpoints.labels() == line_kpoints.ref.labels


def test_grid_kpoints_labels_without_data(grid_kpoints):
    actual = grid_kpoints.labels()
    assert actual is None


def test_line_kpoints_labels_without_data(raw_data):
    raw_kpoints = raw_data.kpoint("line")
    actual = Kpoint.from_data(raw_kpoints).labels()
    ref = [""] * len(raw_kpoints.coordinates)
    ref[0] = r"$[0 0 0]$"
    ref[4] = r"$[0 0 \frac{1}{2}]$"
    ref[5] = r"$[0 0 \frac{1}{2}]$"
    ref[9] = r"$[\frac{1}{2} \frac{1}{2} \frac{1}{2}]$"
    ref[10] = r"$[0 0 0]$"
    ref[14] = r"$[\frac{1}{2} \frac{1}{2} 0]$"
    ref[15] = r"$[\frac{1}{2} \frac{1}{2} 0]$"
    ref[19] = r"$[\frac{1}{2} \frac{1}{2} \frac{1}{2}]$"
    assert actual == ref


def test_explicit_kpoints_distances(explicit_kpoints, Assert):
    actual_distances = explicit_kpoints.distances()
    Assert.allclose(actual_distances, explicit_kpoints.ref.distances)


def test_line_kpoints_labels_distances(line_kpoints, Assert):
    actual_distances = line_kpoints.distances()
    Assert.allclose(actual_distances, line_kpoints.ref.distances)


def test_qpoints_distances(qpoints, Assert):
    actual_distances = qpoints.distances()
    Assert.allclose(actual_distances, qpoints.ref.distances)


def test_grid_kpoints_path_indices(grid_kpoints):
    indices = grid_kpoints.path_indices((0, 0, 0), (0, 0, 1))
    expected = np.array([0, 1, 2, 3])
    assert all(indices == expected)
    indices = grid_kpoints.path_indices((0, 0, 0.125), (0.75, 1, 0.875))
    expected = np.array([0, 17, 34])
    assert all(indices == expected)


def test_print(explicit_kpoints, format_):
    actual, _ = format_(explicit_kpoints)
    reference = """
k-points
48
reciprocal
0.0 0.0 0.125  0
0.0 0.0 0.375  1
0.0 0.0 0.625  2
0.0 0.0 0.875  3
0.0 0.3333333333333333 0.125  4
0.0 0.3333333333333333 0.375  5
0.0 0.3333333333333333 0.625  6
0.0 0.3333333333333333 0.875  7
0.0 0.6666666666666666 0.125  8
0.0 0.6666666666666666 0.375  9
0.0 0.6666666666666666 0.625  10
0.0 0.6666666666666666 0.875  11
0.25 0.0 0.125  12
0.25 0.0 0.375  13
0.25 0.0 0.625  14
0.25 0.0 0.875  15
0.25 0.3333333333333333 0.125  16
0.25 0.3333333333333333 0.375  17
0.25 0.3333333333333333 0.625  18
0.25 0.3333333333333333 0.875  19
0.25 0.6666666666666666 0.125  20
0.25 0.6666666666666666 0.375  21
0.25 0.6666666666666666 0.625  22
0.25 0.6666666666666666 0.875  23
0.5 0.0 0.125  24
0.5 0.0 0.375  25
0.5 0.0 0.625  26
0.5 0.0 0.875  27
0.5 0.3333333333333333 0.125  28
0.5 0.3333333333333333 0.375  29
0.5 0.3333333333333333 0.625  30
0.5 0.3333333333333333 0.875  31
0.5 0.6666666666666666 0.125  32
0.5 0.6666666666666666 0.375  33
0.5 0.6666666666666666 0.625  34
0.5 0.6666666666666666 0.875  35
0.75 0.0 0.125  36
0.75 0.0 0.375  37
0.75 0.0 0.625  38
0.75 0.0 0.875  39
0.75 0.3333333333333333 0.125  40
0.75 0.3333333333333333 0.375  41
0.75 0.3333333333333333 0.625  42
0.75 0.3333333333333333 0.875  43
0.75 0.6666666666666666 0.125  44
0.75 0.6666666666666666 0.375  45
0.75 0.6666666666666666 0.625  46
0.75 0.6666666666666666 0.875  47
    """.strip()
    assert actual == {"text/plain": reference}


def test_factory_methods(raw_data, check_factory_methods):
    data = raw_data.kpoint("automatic")
    parameters = {"path_indices": {"start": (0, 0, 0), "finish": (1, 1, 1)}}
    check_factory_methods(Kpoint, data, parameters)
