"""D2: eğitilen model kalıcı olmalı ve servis onu bulabilmeli."""
import csv
import json
import math
from types import SimpleNamespace

import pytest

from app.services import trainer as module
from app.services.xau_dataset_service import FEATURES, HORIZONS


def _dataset(path, count=320):
    rows = []
    for i in range(count):
        # deterministik, hafif sinyalli seri: eğitim anlamlı sürede bitsin
        base = {name: math.sin(i / (7 + index)) * 0.1 for index, name in enumerate(FEATURES)}
        row = {"date": f"2024-01-{(i % 28) + 1:02d}", "xauusd_close": 2000 + i}
        row.update(base)
        for horizon in HORIZONS:
            row[f"target_return_{horizon}d"] = "" if i >= count - horizon else base[FEATURES[0]] * 0.5
        rows.append(row)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return path


@pytest.fixture
def trained(tmp_path, monkeypatch):
    model_dir = tmp_path / "models"
    monkeypatch.setattr(module, "settings", SimpleNamespace(model_dir=model_dir, keep_artifacts=3))
    dataset = _dataset(tmp_path / "set.csv")
    return module, model_dir, dataset


def test_artifact_lands_in_model_dir_with_pointer(trained):
    module_, model_dir, dataset = trained
    metadata = module_.train_model(epochs=60, minimum_rows=200, dataset_path=dataset)

    artifact = model_dir / f"{metadata['version']}.joblib"
    assert artifact.exists(), "artefakt MODEL_DIR'e yazılmalı (Docker'da kalıcı volume)"

    pointer = model_dir / "active.json"
    assert pointer.exists(), "active.json yazılmalı; model_service onu okuyor"
    assert json.loads(pointer.read_text())["artifact_path"] == str(artifact)


def test_old_artifacts_are_pruned(trained):
    module_, model_dir, dataset = trained
    for _ in range(5):
        module_.train_model(epochs=60, minimum_rows=200, dataset_path=dataset)
    artifacts = sorted(model_dir.glob("*.joblib"))
    assert len(artifacts) <= 3, "saatlik eğitim artefaktları sınırsız birikmemeli"
    # active.json dışındaki her .json bir artefakta ait olmalı; yetim kalmamalı
    sidecars = {path.stem for path in model_dir.glob("*.json")} - {"active"}
    assert sidecars == {path.stem for path in artifacts}


def test_explicit_path_still_wins(trained, tmp_path):
    module_, model_dir, dataset = trained
    target = tmp_path / "bundled.joblib"
    module_.train_model(epochs=60, minimum_rows=200, dataset_path=dataset, artifact_path=target)
    assert target.exists()
    assert not (model_dir / "active.json").exists(), "imaj build'i volume'a pointer yazmamalı"
