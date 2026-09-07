"""
Statistical analysis layer: an OLS regression of daily charging demand on
weather, traffic and calendar effects (quantifying the drivers a business
stakeholder would ask about -- "does cold weather really drive more
charging?"), plus z-score-based anomaly detection on station utilization.

Run (after `dbt run`):
    python python/stats_demand_drivers.py
"""
import duckdb
import numpy as np
import pandas as pd
import statsmodels.api as sm

from common import DB_PATH, OUT_DIR


def get_con():
    return duckdb.connect(str(DB_PATH), read_only=True)


def demand_drivers_regression(con) -> pd.DataFrame:
    df = con.execute("""
        select sessions_count, temp_avg_c, precipitation_mm, congestion_index, is_weekend
        from main_analytics.city_daily_demand
        where temp_avg_c is not null and congestion_index is not null
    """).df()

    X = df[["temp_avg_c", "precipitation_mm", "congestion_index"]].copy()
    X["is_weekend"] = df["is_weekend"].astype(int)
    X = sm.add_constant(X)
    y = df["sessions_count"]

    model = sm.OLS(y, X).fit()

    summary = pd.DataFrame({
        "driver": model.params.index,
        "coefficient": model.params.values,
        "p_value": model.pvalues.values,
        "significant_at_5pct": model.pvalues.values < 0.05,
    })
    summary.to_csv(OUT_DIR / "demand_drivers_regression.csv", index=False)

    with open(OUT_DIR / "demand_drivers_regression_summary.txt", "w", encoding="utf-8") as f:
        f.write(model.summary().as_text())
        f.write(f"\n\nR-squared: {model.rsquared:.3f}\n")

    return summary


def station_utilization_anomalies(con) -> pd.DataFrame:
    df = con.execute("""
        select station_id, city_name, session_date, utilization_rate
        from main_analytics.station_utilization
    """).df()

    df["z_utilization"] = df.groupby("station_id")["utilization_rate"].transform(
        lambda s: (s - s.mean()) / s.std(ddof=0) if s.std(ddof=0) > 0 else 0
    )
    anomalies = df[df["z_utilization"].abs() > 2.5].sort_values("z_utilization", ascending=False)
    anomalies.to_csv(OUT_DIR / "station_utilization_anomalies.csv", index=False)
    return anomalies


def main():
    con = get_con()

    print("Fitting OLS regression: daily sessions ~ temperature + precipitation + congestion + weekend...")
    summary = demand_drivers_regression(con)
    print(summary.round(4).to_string(index=False))
    print(f"  -> outputs/demand_drivers_regression.csv, outputs/demand_drivers_regression_summary.txt")

    print("\nScanning station-day utilization for statistical outliers (|z| > 2.5)...")
    anomalies = station_utilization_anomalies(con)
    print(f"  {len(anomalies)} station-days flagged -> outputs/station_utilization_anomalies.csv")

    con.close()


if __name__ == "__main__":
    main()
