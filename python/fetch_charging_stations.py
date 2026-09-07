"""
Pulls real public charging-station locations from the Open Charge Map REST
API (https://openchargemap.org, community-maintained global registry) for
each of the platform's 8 European cities.

Open Charge Map now requires a free API key for most endpoints. If
OPENCHARGEMAP_API_KEY is not set (or the call fails for any reason -- rate
limit, network, key revoked), falls back to a deterministic synthetic
station generator so the rest of the pipeline never blocks on network/auth.

Run:
    python python/fetch_charging_stations.py
"""
import os
import sys

import numpy as np
import pandas as pd
import requests

from common import CITIES, CONNECTOR_TYPES, RAW_DIR

API_URL = "https://api.openchargemap.io/v3/poi/"
STATIONS_PER_CITY = 10
OPERATORS = ["IONITY", "Fastned", "Vattenfall InCharge", "Shell Recharge", "Tesla Supercharger",
             "Allego", "EVBox", "Enel X Way", "PlugSurfing", "E.ON Drive"]


def fetch_city_from_api(city_key: str, lat: float, lon: float, api_key: str) -> pd.DataFrame:
    resp = requests.get(API_URL, params={
        "output": "json", "latitude": lat, "longitude": lon,
        "distance": 25, "distanceunit": "KM", "maxresults": STATIONS_PER_CITY,
        "compact": "true", "verbose": "false", "key": api_key,
    }, timeout=15)
    resp.raise_for_status()
    payload = resp.json()
    if not payload:
        raise ValueError("empty response")

    rows = []
    for poi in payload:
        addr = poi.get("AddressInfo") or {}
        conns = poi.get("Connections") or []
        power_kw = max([c.get("PowerKW") or 0 for c in conns], default=0) or 22
        conn_type = conns[0].get("ConnectionType", {}).get("Title", "Type 2") if conns else "Type 2"
        rows.append({
            "station_id": f"OCM-{poi.get('ID')}",
            "station_name": addr.get("Title", f"{city_key}-station"),
            "city_key": city_key,
            "operator": (poi.get("OperatorInfo") or {}).get("Title", "Unknown Operator"),
            "latitude": addr.get("Latitude", lat),
            "longitude": addr.get("Longitude", lon),
            "num_connectors": max(len(conns), 1),
            "connector_type": conn_type,
            "power_kw": power_kw,
            "source": "openchargemap_api",
        })
    return pd.DataFrame(rows)


def generate_synthetic_city(city_key: str, lat: float, lon: float, rng: np.random.Generator) -> pd.DataFrame:
    n = STATIONS_PER_CITY
    jitter_lat = rng.normal(0, 0.06, n)
    jitter_lon = rng.normal(0, 0.10, n)
    power_choices = [11, 22, 50, 150, 300]
    power_weights = [0.20, 0.30, 0.25, 0.15, 0.10]
    rows = []
    for i in range(n):
        power = int(rng.choice(power_choices, p=power_weights))
        rows.append({
            "station_id": f"{city_key.upper()}-{i+1:03d}",
            "station_name": f"{city_key.title()} Charging Hub {i+1}",
            "city_key": city_key,
            "operator": rng.choice(OPERATORS),
            "latitude": round(lat + jitter_lat[i], 5),
            "longitude": round(lon + jitter_lon[i], 5),
            "num_connectors": int(rng.integers(1, 7)),
            "connector_type": rng.choice(CONNECTOR_TYPES, p=[0.5, 0.4, 0.1]),
            "power_kw": power,
            "source": "synthetic",
        })
    return pd.DataFrame(rows)


def main():
    api_key = os.environ.get("OPENCHARGEMAP_API_KEY", "")
    rng = np.random.default_rng(7)
    all_rows = []
    api_hits, synthetic_hits = 0, 0

    for city_key, (name, country, cc, lat, lon, _, _) in CITIES.items():
        df = None
        if api_key:
            try:
                df = fetch_city_from_api(city_key, lat, lon, api_key)
                api_hits += 1
                print(f"  {name}: {len(df)} stations from Open Charge Map API")
            except Exception as exc:
                print(f"  {name}: Open Charge Map fetch failed ({exc}); using synthetic fallback", file=sys.stderr)
        if df is None or df.empty:
            df = generate_synthetic_city(city_key, lat, lon, rng)
            synthetic_hits += 1
        all_rows.append(df)

    out = pd.concat(all_rows, ignore_index=True)
    # deliberate messiness matching real POI exports: a few duplicate rows,
    # inconsistent connector-type casing
    dupes = out.sample(frac=0.03, random_state=1)
    out = pd.concat([out, dupes], ignore_index=True)
    mask = out.sample(frac=0.08, random_state=2).index
    out.loc[mask, "connector_type"] = out.loc[mask, "connector_type"].str.lower()

    out.to_csv(RAW_DIR / "stations_raw.csv", index=False)
    print(f"\nWrote {len(out):,} station rows to {RAW_DIR / 'stations_raw.csv'} "
          f"({api_hits} cities from live API, {synthetic_hits} synthetic)")
    if not api_key:
        print("Note: set OPENCHARGEMAP_API_KEY to pull real station data from openchargemap.org "
              "(free key at https://openchargemap.org/site/develop/api). Using synthetic stations for now.")


if __name__ == "__main__":
    main()
