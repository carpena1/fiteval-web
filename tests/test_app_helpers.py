import numpy as np
import pytest

from fiteval_app.callbacks.helpers import records_to_array
from fiteval_app.callbacks.uncertainty_cb import spec_from_state
from fiteval_core.dataio import DataError
from fiteval_core.uncertainty import UncError


def _cf_args(**kw):
    """Full spec_from_state argument set with defaults."""
    args = dict(method="cf", per=None, err_records=None, err_type=1,
                obs_on=False, obs_dist=0, cvo=None, plubo=None, puubo=None,
                prd_on=False, prd_dist=0, cvp=None, plubp=None, puubp=None)
    args.update(kw)
    return args


def test_spec_per():
    spec = spec_from_state(**_cf_args(method="per", per=0.2))
    assert spec.method == "per" and spec.per == 0.2


def test_spec_per_invalid():
    with pytest.raises(UncError):
        spec_from_state(**_cf_args(method="per", per=1.2))


def test_spec_errfile_column_check():
    with pytest.raises(UncError, match="Column Nr"):
        spec_from_state(**_cf_args(method="errfile",
                                   err_records=[[0.1, 0.2]], err_type=1))
    spec = spec_from_state(**_cf_args(method="errfile",
                                      err_records=[[0.1], [0.2]], err_type=1))
    assert spec.err_data.shape == (2, 1)


def test_spec_cf_obs_normal():
    spec = spec_from_state(**_cf_args(obs_on=True, obs_dist=1, cvo=10))
    assert spec.obs_dist == 1 and spec.cvo == 10 and spec.prd_dist == 0


def test_spec_cf_requires_distribution():
    with pytest.raises(UncError, match="Obs distribution"):
        spec_from_state(**_cf_args(obs_on=True, obs_dist=0))


def test_spec_cf_requires_values():
    with pytest.raises(UncError, match="CVo"):
        spec_from_state(**_cf_args(obs_on=True, obs_dist=1, cvo=None))
    with pytest.raises(UncError, match="LUBp"):
        spec_from_state(**_cf_args(prd_on=True, prd_dist=4, plubp=None))


def test_spec_cf_none_selected():
    with pytest.raises(UncError, match="Obs and/or Prd"):
        spec_from_state(**_cf_args())


def test_records_to_array_blank_cells():
    arr = records_to_array([{"c0": 1, "c1": 2}, {"c0": None, "c1": 4}])
    assert np.isnan(arr[1, 0]) and arr[1, 1] == 4


def test_records_to_array_empty():
    with pytest.raises(DataError):
        records_to_array([])
