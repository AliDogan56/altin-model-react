"""Yeniden üretim kararı (saf fonksiyon). Kural: fiyat eşiği aşınca üret, iki üretim arası en az min_interval;
isteğe bağlı azami yaş (0 = kapalı); `force` ve ilk üretim her zaman geçer."""
from __future__ import annotations

import datetime as dt


def should_regenerate(state: dict, now: dt.datetime, price: float | None, move_pct: float, min_interval_minutes: int, max_age_minutes: int) -> tuple[bool, str]:
    if state.get("force"):
        return True, "force"
    last = state.get("last_generation")
    if not last:
        return True, "first_generation"
    elapsed = (now - dt.datetime.fromisoformat(last)).total_seconds() / 60
    if elapsed < min_interval_minutes:
        return False, f"asgari aralık dolmadı ({elapsed:.0f} < {min_interval_minutes} dk)"
    last_price = state.get("last_generation_price")
    change = abs(price / last_price - 1) * 100 if price is not None and last_price else None
    if change is not None and change >= move_pct:
        return True, f"fiyat %{change:.2f} oynadı (eşik %{move_pct})"
    if max_age_minutes and elapsed >= max_age_minutes:
        return True, f"azami yaş doldu ({elapsed:.0f} ≥ {max_age_minutes} dk)"
    return False, f"değişim {'yok' if change is None else f'%{change:.2f}'} < eşik %{move_pct}; yaş {elapsed:.0f} dk"
