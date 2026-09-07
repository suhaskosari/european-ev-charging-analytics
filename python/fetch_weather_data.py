"""
Pulls real historical daily weather (mean temperature, precipitation) for
each of the platform's 8 cities from the free Open-Meteo Archive API
(https://open-meteo.com, ERA5 reanalysis, no API key required).

Falls back to a deterministic synthetic seasonal-weather generator if the
API is unreachable so the rest of the pipeline never blocks on network
access.

Run:
    python python/fetch_weather_data.py
"""
import sys

import numpy as np
import pandas as pd
import requests

from common import CITIES, END_DATE, RAW_DIR, START_DATE

API_URL = "https://archive-api.open-meteo.com/v1/archive"


def fetch_city_from_api(lat: float, lon: float) -> pd.DataFrame:
    resp = requests.get(API_URL, params={
        "latitude": lat, "longitude": lon,
        "start_date": START_DATE, "end_date": END_DATE,
        "daily": "temperature_2m_mean,precipitation_sum",
        "timezone": "UTC",
    }, timeout=30)
    resp.raise_for_status()
    daily = resp.json()["daily"]
    return pd.DataFrame({
        "date": daily["time"],
        "temp_avg_c": daily["temperature_2m_mean"],
        "precipitation_mm": daily["precipitation_sum"],
    })


def generate_synthetic_city(lat: float, rng: np.random.Generator) -> pd.DataFrame:
    dates = pd.date_range(START_DATE, END_DATE, freq="D")
    day_of_year = dates.dayofyear.to_numpy()
    # crude latitude-scaled seasonal sine wave: higher latitude -> colder mean, bigger swing
    mean_temp = 10 - (lat - 45) * 0.35
    amplitude = 10 + (lat - 45) * 0.25
    seasonal = mean_temp + amplitude * -np.cos(2 * np.pi * (day_of_year - 15) / 365.25)
    noise = rng.normal(0, 2.5, size=len(dates))
    precip = np.clip(rng.gamma(1.2, 2.5, size=len(dates)) - 1.5, 0, None)
    return pd.DataFrame({
        "date": dates.date.astype(str),
        "temp_avg_c": np.round(seasonal + noise, 1),
        "precipitation_mm": np.round(precip, 1),
    })


def main():
    rng = np.random.default_rng(11)
    frames = []
    api_hits = 0

    for city_key, (name, country, cc, lat, lon, _, _) in CITIES.items():
        try:
            df = fetch_city_from_api(lat, lon)
            df["source"] = "open_meteo_api"
            api_hits += 1
            print(f"  {name}: {len(df)} days of real weather from Open-Meteo")
        except Exception as exc:
            print(f"  {name}: Open-Meteo fetch failed ({exc}); using synthetic fallback", file=sys.stderr)
            df = generate_synthetic_city(lat, rng)
            df["source"] = "synthetic"
        df["city_key"] = city_key
        frames.append(df)

    out = pd.concat(frames, ignore_index=True)
    out.to_csv(RAW_DIR / "weather_raw.csv", index=False)
    print(f"\nWrote {len(out):,} weather rows to {RAW_DIR / 'weather_raw.csv'} "
          f"({api_hits}/{len(CITIES)} cities from live API)")


if __name__ == "__main__":
    main()
