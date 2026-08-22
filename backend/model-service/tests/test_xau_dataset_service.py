from datetime import date, timedelta

from app.services.xau_dataset_service import FRED_IDS, Series, XauBar, build_rows


def test_build_rows_keeps_latest_features_and_independent_targets():
    start = date(2024, 1, 1)
    bars = [XauBar(start + timedelta(days=i), 101 + i, 99 + i, 100 + i) for i in range(220)]
    macro = {key: Series([(start - timedelta(days=400), 100.0), (start + timedelta(days=220), 101.0)])
             for key in FRED_IDS}
    rows = build_rows(bars, macro)
    assert rows
    assert "target_return_7d" in rows[0]
    assert "target_return_14d" in rows[0]
    assert "target_return_30d" in rows[0]
    assert rows[-1]["target_return_7d"] == ""
    assert rows[-1]["target_return_14d"] == ""
    assert rows[-1]["target_return_30d"] == ""
    assert rows[-1]["date"] == bars[-1].day.isoformat()
