"""
Builds docs/index.html, the interactive GitHub Pages explorer, from the warehouse and the validation outputs.

The page is one self-contained file: all data is embedded as JSON, so it works from GitHub Pages or a local
file with no backend. Nothing on it is hand-typed; re-run after the eval_* scripts.

Run:
    python python/build_dashboard.py
"""
import json

import duckdb
import numpy as np
import pandas as pd

from common import BASE, CITIES, DB_PATH, OUT_DIR

DOCS = BASE / "docs"
BUILD = DOCS / "_build"


def r2(x, d=2):
    return None if pd.isna(x) else round(float(x), d)


def build_data() -> dict:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    daily = con.execute("""
        select city_key, strftime(date, '%Y-%m-%d') d, sessions_count s, total_energy_kwh e, total_revenue_eur r,
               temp_avg_c t, precipitation_mm p, congestion_index c
        from main_analytics.city_daily_demand order by city_key, date""").df()
    st = con.execute("""
        select s.station_id, s.city_key, s.station_name, s.operator, s.latitude, s.longitude, s.power_kw, s.num_connectors,
               coalesce(sum(u.sessions_count), 0) sessions, coalesce(avg(u.utilization_rate), 0) util
        from main_marts.dim_station s left join main_analytics.station_utilization u using (station_id)
        group by all order by s.station_id""").df()
    con.close()

    days = sorted(daily["d"].unique())
    series = {}
    for key, g in daily.groupby("city_key"):
        g = g.set_index("d").reindex(days)
        series[key] = {
            "s": [int(v) for v in g["s"].fillna(0)],
            "e": [round(float(v), 1) for v in g["e"].fillna(0)],
            "r": [round(float(v), 1) for v in g["r"].fillna(0)],
            "t": [r2(v, 1) for v in g["t"].ffill().bfill()],
            "p": [r2(v, 1) or 0 for v in g["p"].fillna(0)],
            "c": [r2(v, 1) for v in g["c"].ffill().bfill()],
        }

    cities = [{"key": k, "name": v[0], "lat": v[3], "lon": v[4]} for k, v in CITIES.items()]

    fc = pd.read_csv(OUT_DIR / "charging_demand_forecast.csv")
    forecast = {k: {"dates": g["date"].tolist(), "vals": [round(float(x), 2) for x in g["forecast_sessions"]]} for k, g in fc.groupby("city_key")}
    tot = fc.groupby("date")["forecast_sessions"].sum()
    forecast["_all"] = {"dates": tot.index.tolist(), "vals": [round(float(x), 2) for x in tot.values]}

    bt = pd.read_csv(OUT_DIR / "forecast_backtest_detail.csv")
    all_w = (bt.groupby("model")["abs_err"].sum() / bt.groupby("model")["actual_sum"].sum()).round(4).to_dict()
    city_w = {c: ((g.groupby("model")["abs_err"].sum() / g.groupby("model")["actual_sum"].sum()).round(4).to_dict()) for c, g in bt.groupby("city")}
    mase = bt.groupby("model")["mase"].mean().round(3).to_dict()

    dm = json.loads((OUT_DIR / "demand_model_validation.json").read_text())
    geo = json.loads((OUT_DIR / "geospatial_stress_test.json").read_text())
    cand = pd.read_csv(OUT_DIR / "station_expansion_candidates.csv")

    return {
        "days": days,
        "cities": cities,
        "series": series,
        "stations": [{"id": r.station_id, "city": r.city_key, "name": r.station_name, "operator": r.operator,
                      "lat": float(r.latitude), "lon": float(r.longitude), "kw": int(r.power_kw), "conn": int(r.num_connectors),
                      "sessions": int(r.sessions), "util": float(r.util)} for r in st.itertuples()],
        "candidates": [{"city": r.city_key, "lat": float(r.candidate_latitude), "lon": float(r.candidate_longitude),
                        "km": float(r.nearest_existing_station_km), "flag": bool(r.expansion_candidate)} for r in cand.itertuples()],
        "forecast": forecast,
        "backtest": {"all": all_w, "city": city_w, "mase": mase},
        "model": {"params": dm["params"], "mean_sessions": dm["mean_sessions"], "ols_temp_pct_per_degree": dm["ols_temp_pct_per_degree"],
                  "recovery": dm["recovery"], "n_inside": dm["n_inside"], "cong_median": float(daily["c"].median())},
        "geo": geo,
    }


def main():
    data = build_data()
    html = (BUILD / "explorer_template.html").read_text(encoding="utf-8")
    html = html.replace("{{CSS}}", (BUILD / "dashboard.css").read_text(encoding="utf-8"))
    html = html.replace("{{DATA}}", json.dumps(data, separators=(",", ":")).replace("</", "<\\/"))
    (DOCS / "index.html").write_text(html, encoding="utf-8")
    print(f"Wrote {DOCS / 'index.html'} ({len(html)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
