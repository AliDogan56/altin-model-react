"""D2: eğitilen model kalıcı olmalı ve servis onu bulabilmeli."""
import csv
import json
import math
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.services import trainer as module
from app.services.xau_dataset_service import FEATURES, HORIZONS


def _dataset(path, count=600):
    rows = []
    for i in range(count):
        # deterministik, hafif sinyalli seri: eğitim anlamlı sürede bitsin
        base = {name: math.sin(i / (7 + index)) * 0.1 for index, name in enumerate(FEATURES)}
        row = {"date": (date(2020, 1, 1) + timedelta(days=i)).isoformat(), "xauusd_close": 2000 + i}
        row.update(base)
        row["gold_volatility_20d"] = 0.2 + abs(base["gold_volatility_20d"])
        for horizon in HORIZONS:
            row[f"target_return_{horizon}d"] = "" if i >= count - horizon else (2000 + i + horizon) / (2000 + i) - 1
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


def test_artifact_is_candidate_and_never_writes_active_pointer(trained):
    module_, model_dir, dataset = trained
    metadata = module_.train_model(epochs=60, minimum_rows=200, dataset_path=dataset)

    artifact = model_dir / f"{metadata['version']}.joblib"
    assert artifact.exists(), "artefakt MODEL_DIR'e yazılmalı (Docker'da kalıcı volume)"

    pointer = model_dir / "active.json"
    assert not pointer.exists(), "aday eğitim aktif modeli değiştirmemeli"
    assert metadata["candidate"] is True
    assert metadata["promoted"] is False
    assert json.loads((model_dir / "last_candidate.json").read_text())["artifact_path"] == str(artifact)
    assert len(metadata["dataset_hash"]) == 64
    assert metadata["preprocessing_version"] == "standard-clip-v1"
    assert metadata["random_seeds"] == [17, 42, 91]


def test_old_artifacts_are_pruned(trained):
    module_, model_dir, dataset = trained
    for _ in range(5):
        module_.train_model(epochs=60, minimum_rows=200, dataset_path=dataset)
    artifacts = sorted(model_dir.glob("*.joblib"))
    assert len(artifacts) <= 3, "saatlik eğitim artefaktları sınırsız birikmemeli"
    # active.json dışındaki her .json bir artefakta ait olmalı; yetim kalmamalı
    sidecars = {path.stem for path in model_dir.glob("*.json")} - {"active", "last_candidate"}
    assert sidecars == {path.stem for path in artifacts}


def test_explicit_path_still_wins(trained, tmp_path):
    module_, model_dir, dataset = trained
    target = tmp_path / "bundled.joblib"
    module_.train_model(epochs=60, minimum_rows=200, dataset_path=dataset, artifact_path=target)
    assert target.exists()
    assert not (model_dir / "active.json").exists(), "imaj build'i volume'a pointer yazmamalı"


def test_candidate_cannot_overwrite_a_champion(trained):
    module_, model_dir, dataset = trained
    model_dir.mkdir()
    champion = model_dir / "champion.joblib"
    champion.write_bytes(b"existing champion")
    pointer = model_dir / "active.json"
    pointer.write_text(json.dumps({"artifact_path": str(champion)}))
    before = pointer.read_bytes()
    module_.train_model(epochs=60, minimum_rows=200, dataset_path=dataset)
    assert champion.read_bytes() == b"existing champion"
    assert pointer.read_bytes() == before
    with pytest.raises(ValueError, match="promotion"):
        module_.train_model(dataset_path=dataset, promote=True)
