"""
Synthetic data generator for the sources that have no convenient free public
API: city/geography reference, EV registration statistics, day-ahead-style
energy prices, city traffic congestion, and -- the core fact table --
charging sessions.

Charging-session volume is deliberately driven by station power, weekday
pattern, local weather (colder -> more frequent charging, a real EV range
effect) and traffic congestion, so the statistics layer (`stats_demand_drivers.py`)
has genuine, recoverable relationships to find rather than pure noise.

Must run AFTER fetch_charging_stations.py and fetch_weather_data.py (it
joins against data/raw/stations_raw.csv and data/raw/weather_raw.csv).

Deliberately injects the kind of messiness a real multi-system export has:
duplicate rows, missing energy readings, mixed timestamp formats,
inconsistent categorical casing, and a handful of sign-error costs -- so the
cleaning layer (etl_clean_transform.py) and dbt tests have real work to do.

Run:
    python python/generate_data.py
"""
import numpy as np
import pandas as pd

from common import CITIES, CONNECTOR_TYPES, END_DATE, RAW_DIR, START_DATE

RNG = np.random.default_rng(42)
DATES = pd.date_range(START_DATE, END_DATE, freq="D")
COUNTRIES = sorted({v[2] for v in CITIES.values()})  # country codes
COUNTRY_NAMES = {v[2]: v[1] for v in CITIES.values()}


def write_cities():
    rows = [{
        "city_key": k, "city_name": v[0], "country": v[1], "country_code": v[2],
        "latitude": v[3], "longitude": v[4], "population_millions": v[5], "region": v[6],
    } for k, v in CITIES.items()]
    df = pd.DataFrame(rows)
    df.to_csv(RAW_DIR / "cities_raw.csv", index=False)
    print(f"  cities_raw.csv: {len(df)} rows")
    return df


def generate_ev_registrations():
    # monthly BEV/PHEV new-registration counts per country, 2024-2025, with a
    # realistic upward adoption curve plus country-level scale and noise
    months = pd.date_range(START_DATE, END_DATE, freq="MS")
    country_scale = {"SE": 9000, "NO": 11000, "DK": 5500, "DE": 42000,
                      "NL": 8500, "FR": 31000, "ES": 12000, "PL": 6000}
    rows = []
    for cc in COUNTRIES:
        base = country_scale.get(cc, 6000)
        for i, m in enumerate(months):
            growth = 1 + 0.028 * i  # ~2.8%/month adoption curve
            seasonal = 1 + 0.15 * np.sin(2 * np.pi * (m.month - 3) / 12)  # spring/year-end bump
            for ev_type, share in [("BEV", 0.68), ("PHEV", 0.32)]:
                noise = RNG.normal(1, 0.08)
                count = max(int(base * share * growth * seasonal * noise), 0)
                rows.append({"country_code": cc, "month": m.strftime("%Y-%m-%d"),
                             "ev_type": ev_type, "registrations": count})
    df = pd.DataFrame(rows)
    df.to_csv(RAW_DIR / "ev_registrations_raw.csv", index=False)
    print(f"  ev_registrations_raw.csv: {len(df)} rows")


def generate_energy_prices():
    # day-ahead-style wholesale price per country: winter peak, weekly
    # pattern, and two deliberate spike windows (cold snap, gas-supply shock)
    rows = []
    base_price = {"SE": 45, "NO": 40, "DK": 70, "DE": 85, "NL": 88, "FR": 75, "ES": 65, "PL": 78}
    for cc in COUNTRIES:
        base = base_price.get(cc, 70)
        day_of_year = DATES.dayofyear.to_numpy()
        seasonal = 1 + 0.35 * -np.cos(2 * np.pi * (day_of_year - 15) / 365.25)
        dow_mult = np.where(DATES.dayofweek.to_numpy() >= 5, 0.85, 1.0)
        noise = RNG.normal(1, 0.12, size=len(DATES))
        price = base * seasonal * dow_mult * noise

        # deliberate spike windows, same idea as the anomaly injections in
        # the sibling e-commerce/fraud repos
        cold_snap = (DATES >= "2024-01-15") & (DATES <= "2024-01-22")
        gas_shock = (DATES >= "2025-02-01") & (DATES <= "2025-02-14")
        price = np.where(cold_snap, price * 2.1, price)
        price = np.where(gas_shock, price * 1.8, price)

        for d, p in zip(DATES, price):
            rows.append({"country_code": cc, "date": d.date().isoformat(),
                         "price_eur_per_mwh": round(float(p), 2)})
    df = pd.DataFrame(rows)
    df.to_csv(RAW_DIR / "energy_prices_raw.csv", index=False)
    print(f"  energy_prices_raw.csv: {len(df)} rows")


def generate_traffic(weather: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for city_key in CITIES:
        w = weather[weather["city_key"] == city_key].set_index("date")
        for d in DATES:
            dstr = d.date().isoformat()
            dow_mult = 0.55 if d.dayofweek >= 5 else 1.0
            rain = float(w["precipitation_mm"].get(dstr, 0) or 0)
            rain_mult = 1 + min(rain / 20, 0.25)
            base = 55 * dow_mult * rain_mult
            congestion = float(np.clip(RNG.normal(base, 8), 5, 100))
            rows.append({"city_key": city_key, "date": dstr, "congestion_index": round(congestion, 1)})
    df = pd.DataFrame(rows)
    df.to_csv(RAW_DIR / "traffic_raw.csv", index=False)
    print(f"  traffic_raw.csv: {len(df)} rows")
    return df


PAYMENT_METHODS = ["App", "RFID Card", "Contactless Card", "Ad-hoc QR"]
COUNTRY_KWH_PRICE = {"SE": 0.38, "NO": 0.32, "DK": 0.48, "DE": 0.52, "NL": 0.50, "FR": 0.44, "ES": 0.40, "PL": 0.36}


def generate_charging_sessions(stations: pd.DataFrame, weather: pd.DataFrame, traffic: pd.DataFrame):
    city_of = {k: v for k, v in CITIES.items()}
    weather_idx = weather.set_index(["city_key", "date"])["temp_avg_c"]
    traffic_idx = traffic.set_index(["city_key", "date"])["congestion_index"]

    power_rate = {11: 0.09, 22: 0.14, 50: 0.24, 150: 0.38, 300: 0.5}
    dstrs = [d.date().isoformat() for d in DATES]
    dows = DATES.dayofweek.to_numpy()

    session_rows = []
    for _, st in stations.drop_duplicates("station_id").iterrows():
        city_key = st["city_key"]
        base_rate = power_rate.get(int(st["power_kw"]) if not pd.isna(st["power_kw"]) else 22, 0.55)
        n_conn = max(int(st["num_connectors"]) if not pd.isna(st["num_connectors"]) else 1, 1)

        for d, dstr, dow in zip(DATES, dstrs, dows):
            temp = weather_idx.get((city_key, dstr), 10.0)
            cong = traffic_idx.get((city_key, dstr), 50.0)
            weekday_mult = 1.15 if dow < 5 else 0.9
            cold_mult = 1 + max(0, (10 - temp)) * 0.015   # colder -> more frequent charging (range anxiety)
            traffic_mult = 1 + (cong - 50) * 0.003

            lam = base_rate * n_conn * weekday_mult * cold_mult * traffic_mult
            n_sessions = RNG.poisson(max(lam, 0.02))
            if n_sessions == 0:
                continue

            for _ in range(n_sessions):
                # bimodal start time: commute peaks + some overnight residential-style charging
                bucket = RNG.choice(["morning", "evening", "overnight", "midday"], p=[0.28, 0.32, 0.20, 0.20])
                hour = {
                    "morning": RNG.normal(8, 1.2), "evening": RNG.normal(18.5, 1.5),
                    "overnight": RNG.normal(23, 2.5) % 24, "midday": RNG.normal(13, 2),
                }[bucket]
                hour = float(np.clip(hour, 0, 23.98))
                start_dt = d + pd.Timedelta(hours=hour)

                power_kw = float(st["power_kw"]) if not pd.isna(st["power_kw"]) else 22.0
                target_kwh = RNG.gamma(2.2, 8.0) if power_kw >= 50 else RNG.gamma(2.5, 5.0)
                target_kwh = float(np.clip(target_kwh * (1 + max(0, (10 - temp)) * 0.01), 2, 95))
                duration_min = max((target_kwh / power_kw) * 60 * RNG.normal(1.15, 0.1), 5)
                energy_kwh = round(target_kwh, 2)
                price_per_kwh = COUNTRY_KWH_PRICE.get(city_of[city_key][2], 0.42) * RNG.normal(1, 0.05)
                cost_eur = round(energy_kwh * price_per_kwh, 2)

                session_rows.append({
                    "session_id": None,
                    "station_id": st["station_id"],
                    "city_key": city_key,
                    "start_time": start_dt,
                    "duration_min": round(duration_min, 1),
                    "energy_kwh": energy_kwh,
                    "cost_eur": cost_eur,
                    "connector_type": st["connector_type"],
                    "payment_method": RNG.choice(PAYMENT_METHODS, p=[0.45, 0.20, 0.25, 0.10]),
                })

    df = pd.DataFrame(session_rows)
    df = df.sort_values("start_time").reset_index(drop=True)
    df["session_id"] = [f"SESS-{i+1:07d}" for i in range(len(df))]

    # --- deliberate messiness -------------------------------------------------
    n = len(df)

    # 1) mixed timestamp formats on a subset of rows (as string, matching a
    #    second source system's export convention)
    df["start_time"] = df["start_time"].astype(str)
    alt_fmt_idx = df.sample(frac=0.15, random_state=3).index
    df.loc[alt_fmt_idx, "start_time"] = pd.to_datetime(df.loc[alt_fmt_idx, "start_time"]).dt.strftime("%d/%m/%Y %H:%M")

    # 2) missing energy_kwh (meter read failures)
    missing_idx = df.sample(frac=0.03, random_state=4).index
    df.loc[missing_idx, "energy_kwh"] = np.nan

    # 3) sign-error costs (billing system bug -- refund coded as negative source amount)
    sign_idx = df.sample(frac=0.01, random_state=5).index
    df.loc[sign_idx, "cost_eur"] = -df.loc[sign_idx, "cost_eur"].abs()

    # 4) inconsistent categorical casing
    case_idx = df.sample(frac=0.10, random_state=6).index
    df.loc[case_idx, "payment_method"] = df.loc[case_idx, "payment_method"].str.upper()

    # 5) duplicate rows (retry-on-timeout double-write, a common charge-point
    #    operator (CPO) integration bug)
    dupes = df.sample(frac=0.015, random_state=7)
    df = pd.concat([df, dupes], ignore_index=True)

    df.to_csv(RAW_DIR / "charging_sessions_raw.csv", index=False)
    print(f"  charging_sessions_raw.csv: {len(df):,} rows ({n:,} unique sessions before injected duplicates)")


def main():
    print("Generating geographic reference...")
    write_cities()

    print("Generating EV registration statistics...")
    generate_ev_registrations()

    print("Generating energy price series...")
    generate_energy_prices()

    weather = pd.read_csv(RAW_DIR / "weather_raw.csv", dtype={"date": str})
    print("Generating traffic congestion series...")
    traffic = generate_traffic(weather)

    stations = pd.read_csv(RAW_DIR / "stations_raw.csv")
    print("Generating charging sessions (this is the largest table, may take a minute)...")
    generate_charging_sessions(stations, weather, traffic)

    print("\nDone. Raw sources written to data/raw/.")


if __name__ == "__main__":
    main()
