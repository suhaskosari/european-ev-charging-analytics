"""
Pandas cleaning layer: dedupes, normalizes mixed timestamp formats and
categorical casing, imputes missing energy readings, and fixes sign-error
costs across every raw source. Every fix is counted and logged to
outputs/data_quality_report.md.

Run:
    python python/etl_clean_transform.py
"""
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from common import OUT_DIR, PROCESSED_DIR, RAW_DIR

log_lines = ["# Data Quality Report\n", f"_Generated {datetime.now(timezone.utc).isoformat()}_\n"]


def log(section: str, lines: list[str]):
    log_lines.append(f"\n## {section}\n")
    for l in lines:
        log_lines.append(f"- {l}")


def clean_stations() -> pd.DataFrame:
    df = pd.read_csv(RAW_DIR / "stations_raw.csv")
    before = len(df)
    df = df.drop_duplicates(subset="station_id")
    dupes_removed = before - len(df)

    df["connector_type"] = df["connector_type"].str.strip().str.title()
    df["connector_type"] = df["connector_type"].replace({"Chademo": "CHAdeMO", "Ccs": "CCS"})
    df["operator"] = df["operator"].str.strip()

    df.to_csv(PROCESSED_DIR / "stations.csv", index=False)
    log("Stations", [
        f"Removed {dupes_removed} duplicate station_id rows ({before:,} -> {len(df):,}).",
        "Normalized connector_type casing (e.g. 'chademo' -> 'CHAdeMO').",
    ])
    return df


def clean_cities() -> pd.DataFrame:
    df = pd.read_csv(RAW_DIR / "cities_raw.csv")
    df.to_csv(PROCESSED_DIR / "cities.csv", index=False)
    return df


def clean_ev_registrations() -> pd.DataFrame:
    df = pd.read_csv(RAW_DIR / "ev_registrations_raw.csv")
    df["month"] = pd.to_datetime(df["month"]).dt.date.astype(str)
    df.to_csv(PROCESSED_DIR / "ev_registrations.csv", index=False)
    return df


def clean_energy_prices() -> pd.DataFrame:
    df = pd.read_csv(RAW_DIR / "energy_prices_raw.csv")
    df.to_csv(PROCESSED_DIR / "energy_prices.csv", index=False)
    return df


def clean_traffic() -> pd.DataFrame:
    df = pd.read_csv(RAW_DIR / "traffic_raw.csv")
    df.to_csv(PROCESSED_DIR / "traffic.csv", index=False)
    return df


def clean_weather() -> pd.DataFrame:
    df = pd.read_csv(RAW_DIR / "weather_raw.csv")
    before = df["temp_avg_c"].isna().sum()
    if before:
        df["temp_avg_c"] = df.groupby("city_key")["temp_avg_c"].transform(lambda s: s.interpolate().ffill().bfill())
    df.to_csv(PROCESSED_DIR / "weather.csv", index=False)
    if before:
        log("Weather", [f"Interpolated {before} missing daily temperature readings per city."])
    return df


def parse_mixed_timestamp(series: pd.Series) -> pd.Series:
    alt_mask = series.str.contains("/", na=False)
    iso = pd.to_datetime(series.where(~alt_mask), errors="coerce")
    alt = pd.to_datetime(series.where(alt_mask), format="%d/%m/%Y %H:%M", errors="coerce")
    return iso.fillna(alt)


def clean_charging_sessions(stations: pd.DataFrame) -> pd.DataFrame:
    df = pd.read_csv(RAW_DIR / "charging_sessions_raw.csv")
    before = len(df)

    df = df.drop_duplicates(subset="session_id")
    dupes_removed = before - len(df)

    df["start_time"] = parse_mixed_timestamp(df["start_time"])
    bad_ts = df["start_time"].isna().sum()
    df = df.dropna(subset=["start_time"])

    df["payment_method"] = df["payment_method"].str.strip().str.title().replace({"Rfid Card": "RFID Card"})

    sign_errors = int((df["cost_eur"] < 0).sum())
    df["cost_eur"] = df["cost_eur"].abs()

    missing_energy = int(df["energy_kwh"].isna().sum())
    df = df.merge(stations[["station_id", "power_kw"]], on="station_id", how="left")
    # impute missing energy from duration and the station's rated power, capped
    # at a realistic per-session ceiling, rather than a flat mean fill
    est_from_duration = (df["duration_min"] / 60) * df["power_kw"] * 0.85
    df["energy_kwh"] = df["energy_kwh"].fillna(est_from_duration.clip(upper=95).round(2))
    df = df.drop(columns=["power_kw"])

    bad_duration = int((df["duration_min"] <= 0).sum())
    df = df[df["duration_min"] > 0]

    df["date"] = df["start_time"].dt.date.astype(str)
    df["hour"] = df["start_time"].dt.hour

    df.to_csv(PROCESSED_DIR / "charging_sessions.csv", index=False)
    log("Charging Sessions", [
        f"Removed {dupes_removed} duplicate session_id rows ({before:,} -> {before - dupes_removed:,}).",
        f"Parsed 2 mixed timestamp formats (ISO + `dd/mm/yyyy HH:MM`); {bad_ts} unparseable rows dropped.",
        f"Corrected {sign_errors} sign-error costs (billing refund coded as negative charge).",
        f"Imputed {missing_energy} missing energy_kwh readings from duration x rated power (not a flat mean fill).",
        f"Dropped {bad_duration} rows with non-positive duration_min.",
    ])
    return df


def main():
    print("Cleaning stations...")
    stations = clean_stations()
    print("Cleaning cities, EV registrations, energy prices, traffic, weather...")
    clean_cities()
    clean_ev_registrations()
    clean_energy_prices()
    clean_traffic()
    clean_weather()
    print("Cleaning charging sessions (largest table)...")
    sessions = clean_charging_sessions(stations)

    log("Summary", [
        f"{len(stations):,} clean stations across {stations['city_key'].nunique()} cities.",
        f"{len(sessions):,} clean charging sessions retained for the warehouse.",
    ])
    (OUT_DIR / "data_quality_report.md").write_text("\n".join(log_lines), encoding="utf-8")
    print(f"\nWrote data/processed/*.csv and {OUT_DIR / 'data_quality_report.md'}")


if __name__ == "__main__":
    main()
