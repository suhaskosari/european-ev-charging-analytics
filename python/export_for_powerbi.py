"""
Exports the final dbt marts (plus the Python-layer forecast, regression and
geospatial outputs) to CSV so they can be imported directly into Power BI
Desktop (Get Data -> Text/CSV) without needing a live DuckDB ODBC connection.

Run after `dbt run` and the python/forecasting.py, stats_demand_drivers.py,
geospatial_analysis.py scripts:
    python python/export_for_powerbi.py
"""
import shutil

import duckdb

from common import BASE, DB_PATH, OUT_DIR

EXPORT_DIR = BASE / "powerbi" / "exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

TABLES = {
    "dim_city": "main_marts.dim_city",
    "dim_station": "main_marts.dim_station",
    "dim_date": "main_marts.dim_date",
    "fct_charging_sessions": "main_marts.fct_charging_sessions",
    "fct_energy_prices": "main_marts.fct_energy_prices",
    "fct_weather_daily": "main_marts.fct_weather_daily",
    "fct_traffic_daily": "main_marts.fct_traffic_daily",
    "fct_ev_registrations": "main_marts.fct_ev_registrations",
    "station_utilization": "main_analytics.station_utilization",
    "regional_demand_monthly": "main_analytics.regional_demand_monthly",
    "ev_market_growth": "main_analytics.ev_market_growth",
    "city_daily_demand": "main_analytics.city_daily_demand",
}

# Python-layer output CSVs to copy straight through (already in the right shape)
OUTPUT_FILES = [
    "charging_demand_forecast.csv",
    "station_expansion_candidates.csv",
    "station_utilization_anomalies.csv",
    "demand_drivers_regression.csv",
]


def main():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    for name, ref in TABLES.items():
        out_path = EXPORT_DIR / f"{name}.csv"
        con.execute(f"copy (select * from {ref}) to '{out_path.as_posix()}' (header, delimiter ',')")
        rows = con.execute(f"select count(*) from {ref}").fetchone()[0]
        print(f"{name:<26} {rows:>7,} rows -> {out_path.relative_to(BASE)}")
    con.close()

    for fname in OUTPUT_FILES:
        src = OUT_DIR / fname
        if src.exists():
            shutil.copy(src, EXPORT_DIR / fname)
            print(f"{fname:<26} copied from outputs/ -> {(EXPORT_DIR / fname).relative_to(BASE)}")
        else:
            print(f"{fname:<26} SKIPPED (not found -- run the python/*.py analysis scripts first)")


if __name__ == "__main__":
    main()
