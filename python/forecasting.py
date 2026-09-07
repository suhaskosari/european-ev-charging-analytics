"""
Charging-demand forecasting on top of the `analytics.city_daily_demand` dbt
mart: a per-city Holt-Winters (triple exponential smoothing) model with
weekly seasonality, forecasting daily session counts 30 days beyond the
observed data. Writes a per-city forecast CSV, a combined summary, and a
chart for the two highest-volume cities.

Run (after `dbt run`):
    python python/forecasting.py
"""
from pathlib import Path

import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from common import DB_PATH, OUT_DIR

FORECAST_HORIZON_DAYS = 30


def get_con():
    return duckdb.connect(str(DB_PATH), read_only=True)


def load_daily_demand(con) -> pd.DataFrame:
    df = con.execute("""
        select city_key, city_name, date, sessions_count
        from main_analytics.city_daily_demand
        order by city_key, date
    """).df()
    df["date"] = pd.to_datetime(df["date"])
    return df


def forecast_city(series: pd.Series) -> pd.Series:
    model = ExponentialSmoothing(
        series, trend="add", seasonal="add", seasonal_periods=7,
        initialization_method="estimated",
    ).fit(optimized=True)
    forecast = model.forecast(FORECAST_HORIZON_DAYS)
    return forecast.clip(lower=0)


def main():
    con = get_con()
    demand = load_daily_demand(con)
    con.close()

    all_forecasts = []
    for city_key, grp in demand.groupby("city_key"):
        city_name = grp["city_name"].iloc[0]
        series = grp.set_index("date")["sessions_count"].asfreq("D").fillna(0)
        forecast = forecast_city(series)

        fc_df = pd.DataFrame({
            "city_key": city_key,
            "city_name": city_name,
            "date": forecast.index,
            "forecast_sessions": forecast.round(1).values,
            "type": "forecast",
        })
        all_forecasts.append(fc_df)
        print(f"  {city_name}: next-30-day avg forecast = {forecast.mean():.1f} sessions/day "
              f"(recent 30-day actual avg = {series.tail(30).mean():.1f})")

    combined = pd.concat(all_forecasts, ignore_index=True)
    combined.to_csv(OUT_DIR / "charging_demand_forecast.csv", index=False)
    print(f"\nWrote {len(combined):,} forecast rows to {OUT_DIR / 'charging_demand_forecast.csv'}")

    # chart: actual + forecast for the two busiest cities
    top_cities = demand.groupby("city_key")["sessions_count"].sum().nlargest(2).index
    fig, ax = plt.subplots(figsize=(12, 5))
    colors = ["#3b6fa0", "#d1495b"]
    for color, city_key in zip(colors, top_cities):
        actual = demand[demand["city_key"] == city_key].set_index("date")["sessions_count"]
        city_name = demand[demand["city_key"] == city_key]["city_name"].iloc[0]
        actual_7d = actual.rolling(7).mean()
        ax.plot(actual_7d.index, actual_7d.values, color=color, linewidth=1.3, label=f"{city_name} (7d avg, actual)")
        fc = combined[combined["city_key"] == city_key]
        ax.plot(fc["date"], fc["forecast_sessions"], color=color, linewidth=1.3, linestyle="--",
                label=f"{city_name} (forecast)")

    ax.set_title(f"Daily Charging Sessions: 7-Day Rolling Actuals + {FORECAST_HORIZON_DAYS}-Day Forecast")
    ax.set_ylabel("Sessions per day")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "charging_demand_forecast.png", dpi=140)
    plt.close(fig)
    print(f"Wrote {OUT_DIR / 'charging_demand_forecast.png'}")


if __name__ == "__main__":
    main()
