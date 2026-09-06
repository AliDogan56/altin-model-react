"""The audit harness itself must not smuggle future targets into calibration."""
import numpy as np
import pytest

from research import evaluation as e


def fixture():
    rng=np.random.default_rng(141)
    dates=np.datetime64("2020-01-01")+np.arange(500).astype("timedelta64[D]")
    x=rng.normal(size=(500,19));x[:,6]=np.abs(x[:,6])+.1
    y=.01*x[:,0]+rng.normal(scale=.02,size=500)
    return dates,x,y


def test_target_dates_purge_both_boundaries():
    dates,x,y=fixture()
    ends=dates+np.timedelta64(30,"D")
    train,cal,test=e.split_fold(dates,ends,np.arange(500),350,450)
    assert ends[train].max()<dates[cal].min()
    assert ends[cal].max()<dates[test].min()
    assert not np.intersect1d(train,cal).size
    assert not np.intersect1d(cal,test).size


def test_persistence_is_not_a_directional_model():
    result=e.metrics(np.array([.01,-.02,.03]),np.zeros(3))
    assert result["mae_skill"]==0
    assert result["direction"] is None
    assert result["active_fraction"]==0


def test_block_bootstrap_reproducible():
    _,_,y=fixture();p=y*.3
    assert e.block_ci(y,p,repetitions=40)==e.block_ci(y,p,repetitions=40)


def test_conformal_rank_is_finite_sample_conservative():
    assert e.conformal_quantile(np.arange(10),.8)==8


def test_outer_targets_cannot_change_predictions_or_first_interval(monkeypatch):
    dates,x,y=fixture();ends=dates+np.timedelta64(7,"D")
    monkeypatch.setattr(e,"target_end_global",ends)
    train,cal,test=e.split_fold(dates,ends,np.arange(500),350,430)
    args=(e.Spec("test","ridge",calibration="slope"),x,x,np.full(500,2000),y,dates,train,cal,test,7,np.zeros_like(x,dtype=bool))
    p,widths,diag,_=e.fit_spec(*args)
    altered=y.copy();altered[test]+=100
    other=e.fit_spec(*args[:4],altered,*args[5:])
    np.testing.assert_array_equal(p,other[0])
    assert diag["calibration_weight"]==other[2]["calibration_weight"]
    for key in widths: assert widths[key][0]==other[1][key][0]


def test_baseline_only_uses_matured_targets(monkeypatch):
    dates,x,y=fixture();ends=dates+np.timedelta64(30,"D")
    monkeypatch.setattr(e,"target_end_global",ends)
    train,cal,test=e.split_fold(dates,ends,np.arange(500),350,430)
    spec=e.Spec("historical_mean","mean")
    args=(spec,x,x,np.full(500,2000),y,dates,train,cal,test,30,np.zeros_like(x,dtype=bool))
    p=e.fit_spec(*args)[0]
    known=np.flatnonzero(ends<dates[test[0]])
    assert p[0]==pytest.approx(np.mean(y[known]))
    changed=y.copy();changed[ends>=dates[test[0]]]+=100
    assert e.fit_spec(*args[:4],changed,*args[5:])[0][0]==pytest.approx(p[0])


def test_feature_imputation_and_regime_thresholds_use_training_only():
    dates,x,y=fixture();extra=np.full((500,2),np.nan);extra[200:]=1
    train=np.arange(200)
    design,_=e.feature_design(x,dates,extra,"regime",train)
    changed=x.copy();changed[200:]*=1000
    other,_=e.feature_design(changed,dates,extra,"regime",train)
    np.testing.assert_array_equal(design[train],other[train])


def test_price_engineering_is_prefix_invariant():
    dates,x,y=fixture();price=2000*np.exp(np.cumsum(y))
    full,_=e.engineered_features(price,x)
    prefix,_=e.engineered_features(price[:300],x[:300])
    np.testing.assert_allclose(full[:300],prefix,equal_nan=True,rtol=0,atol=0)


def test_short_calibration_fails_instead_of_reusing_residual_labels(monkeypatch):
    dates,x,y=fixture()
    monkeypatch.setattr(e,"target_end_global",dates+np.timedelta64(30,"D"))
    with pytest.raises(ValueError, match="non-overlapping weight/residual"):
        e.fit_spec(e.Spec("small","ridge",calibration="slope"),x,x,np.full(500,2000),y,dates,
                   np.arange(100),np.arange(150,180),np.arange(250,280),30,np.zeros_like(x,dtype=bool))
