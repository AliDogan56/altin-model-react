#!/usr/bin/env python3
"""Read-only integration checks of a trusted, locally generated audit candidate."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import joblib
import numpy as np

from app.services.data_quality import DataQualityError, assert_promotion_ready, feature_vector
from app.services.model_service import ModelService
from app.services.freshness import frozen_features
from app.services.preprocessing import transform_features
from app.services.trainer import _load_dataset, _training_code_hash
from research.evaluation import load_snapshot


def main(directory):
    candidate_path = directory / 'candidate/xauusd_candidate_checked.joblib'
    candidate = joblib.load(candidate_path)  # only this workflow's trusted output
    manifest = json.loads((directory/'manifest.json').read_text())
    metadata = json.loads(candidate_path.with_suffix('.json').read_text())
    snapshot = directory/'dataset_snapshot.csv'
    digest = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    assert digest == manifest['dataset_hash'] == candidate['dataset_hash']
    assert candidate['training_code_hash'] == _training_code_hash()
    assert manifest['evaluator_sha256'] == hashlib.sha256((ROOT/'research/evaluation.py').read_bytes()).hexdigest()
    assert candidate['version'] == metadata['version']
    assert candidate['candidate'] is True and candidate['promoted'] is False
    assert ModelService._schema_error(candidate) is None
    try:
        assert_promotion_ready(snapshot)
    except DataQualityError:
        promotion_blocked = True
    else:
        raise AssertionError('Unverified snapshot must not pass the promotion gate')
    load_snapshot(snapshot)  # stored targets must match observed maturity prices
    rows, _ = _load_dataset(snapshot)
    features = dict(zip(candidate['features'], feature_vector(rows[-1])))
    instance = ModelService.__new__(ModelService)
    instance.active = candidate
    instance.version = candidate['version']
    first = instance.predict(features, float(rows[-1]['xauusd_close']))
    second = instance.predict(features, float(rows[-1]['xauusd_close']))
    assert first == second
    max_delta = 0.0
    for i, h in enumerate(candidate['horizons']):
        state = candidate['per_horizon'][h]
        x = transform_features(feature_vector(rows[-1]), state['x_mean'], state['x_std'])
        direct = state['weight'] * np.mean([m.predict(x.reshape(1,-1))[0] for m in state['networks']])
        max_delta = max(max_delta, abs(float(direct)-first['mean'][i]))
        assert np.isclose(first['mean'][i], metadata['metrics'][str(h)]['latest_fit_return'], rtol=0, atol=1e-12)
        for fold in candidate['validation'][str(h)]['folds']:
            assert fold['train']['last_target'] < fold['weight_calibration']['start']
            assert fold['weight_calibration']['last_target'] < fold['interval_calibration']['start']
            assert fold['interval_calibration']['last_target'] < fold['test']['start']
    assert max_delta == 0.0
    results = json.loads((directory/'results.json').read_text())
    assert len(results) == 3 and all(len(v) == 43 for v in results.values())
    legacy_check = None
    legacy_path = ROOT/'data/xauusd_model.joblib'
    if legacy_path.exists():
        legacy = joblib.load(legacy_path)
        legacy_instance = ModelService.__new__(ModelService)
        legacy_instance.active, legacy_instance.version = legacy, legacy['version']
        neutral = frozen_features(rows, legacy['features'][8:])
        response = legacy_instance.predict(features, float(rows[-1]['xauusd_close']), neutral)
        means, errors = [], []
        for horizon in legacy['horizons']:
            state = legacy['per_horizon'][horizon]
            z = np.clip((np.asarray(feature_vector(rows[-1]))-state['x_mean'])/state['x_std'], -6, 6)
            for name in neutral:
                z[legacy['features'].index(name)] = 0.0
            networks = state.get('networks') or [state['network']]
            means.append(float(state.get('weight',1))*np.mean([network.predict(z.reshape(1,-1))[0] for network in networks]))
            vol = float(features['gold_volatility_20d'])
            reference = max(float(state.get('training_volatility',vol)),1e-9)
            errors.append(float(state.get('error80',state.get('error70',.03)))*float(np.clip(vol/reference,.75,2)))
        legacy_check = {'local_legacy_version':legacy['version'],
            'max_mean_delta':float(np.max(np.abs(np.asarray(means)-response['mean']))),
            'max_error_delta':float(np.max(np.abs(np.asarray(errors)-response['error']))),
            'scope':'local bundled legacy artifact; not a read/write of the production artifact'}
        assert legacy_check['max_mean_delta'] == legacy_check['max_error_delta'] == 0.0
    evidence = {'status':'PASS', 'dataset_sha256':digest, 'model_version':candidate['version'],
        'training_code_hash_matches':True, 'evaluator_hash_matches':True,
        'candidate_schema_valid':True, 'candidate_serving_deterministic':True,
        'latest_training_vs_serving_max_absolute_delta':max_delta,
        'candidate_all_9_fold_maturity_boundaries_valid':True,
        'unverified_dataset_promotion_blocked':promotion_blocked,
        'experiments':129, 'promoted':False, 'legacy_compatibility':legacy_check,
        'note':'Diagnostics only: no claim of true point-in-time macro or spot provenance. No network, training, or active model writes.'}
    (directory/'integration_verification.json').write_text(json.dumps(evidence, indent=2)+'\n')
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    main(parser.parse_args().directory)
