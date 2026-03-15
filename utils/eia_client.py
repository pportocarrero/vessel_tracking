"""EIA Open Data API — WTI & Brent crude spot prices."""

import requests
import random
from datetime import datetime, timezone, timedelta

EIA_BASE = "https://api.eia.gov/v2/petroleum/pri/spt/data/"


def fetch_oil_prices(api_key: str, demo_mode: bool = False) -> list[dict]:
    if demo_mode or api_key == "DEMO":
        return _demo_prices()
    try:
        params = {
            "api_key": api_key,
            "frequency": "daily",
            "data[]": "value",
            "facets[product][]": ["EPCBRENT", "EPCWTI"],
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": 90,
        }
        resp = requests.get(EIA_BASE, params=params, timeout=10)
        resp.raise_for_status()
        rows = resp.json().get("response", {}).get("data", [])
        if not rows:
            return _demo_prices()

        wti_map, brent_map = {}, {}
        for row in rows:
            date    = row.get("period", "")
            product = row.get("product", "")
            value   = row.get("value")
            if value is None:
                continue
            if product == "EPCWTI":
                wti_map[date] = float(value)
            elif product == "EPCBRENT":
                brent_map[date] = float(value)

        dates = sorted(set(list(wti_map) + list(brent_map)))
        return [{"date": d, "wti": wti_map.get(d), "brent": brent_map.get(d)} for d in dates][-90:]
    except Exception:
        return _demo_prices()


def _demo_prices(n_days: int = 90) -> list[dict]:
    random.seed(42)
    base_wti, base_brent = 72.0, 76.5
    prices, wti_val, brent_val = [], base_wti, base_brent
    today = datetime.now(timezone.utc).date()
    for i in range(n_days):
        date = today - timedelta(days=n_days - i - 1)
        tension = 4.5 * ((i - 55) / 15.0) if 55 <= i <= 70 else (4.5 * (1 - (i - 70) / 10.0) if 70 < i <= 80 else 0.0)
        wti_val   = wti_val   * 0.98 + base_wti   * 0.02 + random.gauss(0, 0.8) + tension * 0.3
        brent_val = max(brent_val * 0.98 + base_brent * 0.02 + random.gauss(0, 0.7) + tension * 0.3, wti_val + 1.5)
        prices.append({"date": date.strftime("%Y-%m-%d"), "wti": round(wti_val, 2), "brent": round(brent_val, 2)})
    return prices
