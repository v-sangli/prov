import time

import pytest

from prov.core.ids import kind_of, new_id


def test_format_and_kind():
    i = new_id("checkpoint")
    assert i.startswith("ckpt_") and len(i) == len("ckpt_") + 26
    assert kind_of(i) == "checkpoint"


def test_calibration_kind():
    i = new_id("calibration")
    assert i.startswith("calib_") and kind_of(i) == "calibration"


def test_unique():
    assert len({new_id("run") for _ in range(10_000)}) == 10_000


def test_sorts_by_creation_time():
    a = new_id("run")
    time.sleep(0.002)
    b = new_id("run")
    assert a < b


@pytest.mark.parametrize("bad", ["run_123", "xyz_01J00000000000000000000000", "run-01J0000000000000000000000"])
def test_rejects_bad_ids(bad):
    with pytest.raises(ValueError):
        kind_of(bad)
