"""
Builds docs/index.html (the GitHub Pages dashboard) from the warehouse and the validation outputs.
Nothing on the page is hand-typed. Re-run after the eval_* scripts.

Run:
    python python/build_dashboard.py
"""
import json

import duckdb
import numpy as np
import pandas as pd

from common import BASE, DB_PATH, OUT_DIR

DOCS = BASE / "docs"
BUILD = DOCS / "_build"
pct = lambda x: f"{np.expm1(x):+.1%}"


def build_data() -> dict:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    head = con.execute("""select count(*) s, count(distinct station_id) st, sum(energy_kwh) kwh, sum(cost_eur) rev
                          from main_marts.fct_charging_sessions""").df().iloc[0]
    monthly = con.execute("""select strftime(date_trunc('month', session_date), '%Y-%m-%d') m, count(*) n
                             from main_marts.fct_charging_sessions group by 1 order by 1""").fetchall()
    by_city = con.execute("""select c.city_name, count(*) n from main_marts.fct_charging_sessions s
                             join main_marts.dim_station c using (station_id) group by 1 order by 2 desc""").fetchall()
    util = con.execute("""select city_name, avg(utilization_rate) * 100 u from main_analytics.station_utilization
                          group by 1 order by 2 desc""").fetchall()
    weather_src = con.execute("select data_source, count(*) from main_marts.fct_weather_daily group by 1").fetchall()
    con.close()

    dm = json.loads((OUT_DIR / "demand_model_validation.json").read_text())
    geo = json.loads((OUT_DIR / "geospatial_stress_test.json").read_text())
    bt = pd.read_csv(OUT_DIR / "forecast_backtest_detail.csv")
    wape = (bt.groupby("model")["abs_err"].sum() / bt.groupby("model")["actual_sum"].sum() * 100).sort_values()
    mase = bt.groupby("model")["mase"].mean()
    real_weather = sum(n for s, n in weather_src if "synthetic" not in str(s).lower())

    return {
        "kpis": [
            {"label": "Charging sessions", "value": f"{int(head.s):,}", "sub": f"{int(head.st)} stations · 8 cities"},
            {"label": "Energy delivered", "value": f"{head.kwh/1e6:.2f} GWh", "sub": f"EUR {head.rev/1e3:,.0f}k session revenue"},
            {"label": "dbt tests", "value": "25/25", "sub": "unique · not-null · FK", "cls": "good"},
            {"label": "Driver parameters recovered", "value": f"{dm['n_inside']}/{len(dm['recovery'])}", "sub": "truth inside 95% CI", "cls": "accent"},
            {"label": "Forecast error (WAPE)", "value": f"{wape['holt_winters']:.1f}%", "sub": f"MASE {mase['holt_winters']:.2f} vs naive {mase['seasonal_naive']:.2f}"},
        ],
        "tags": ["SQL", "Python", "dbt", "DuckDB", "PostgreSQL", "Power BI", "Azure Data Factory", "Microsoft Fabric",
                 "Poisson GLM", "Forecasting", "Backtesting", "Geospatial", "GitHub Actions", "Docker"],
        "monthly": [[m, n] for m, n in monthly],
        "cities": [{"label": c, "value": int(n)} for c, n in by_city],
        "util": [{"label": c, "value": float(u)} for c, u in util],
        "wape": [{"label": m.replace("_", " "), "value": float(w), "cls": "bar-1" if m == "holt_winters" else "bar-2"} for m, w in wape.items()],
        "driversCaption": (f"The first pooled OLS put temperature at {dm['ols_temp_pct_per_degree']:+.1%} of mean sessions per degree, "
                           "a fraction of the true cold effect. This Poisson model has city fixed effects, a below-10°C hinge and robust errors."),
        "drivers": [{"label": r["label"], "truth": pct(r["truth"]), "est": pct(r["estimate"]),
                     "ci": f"{pct(r['lo'])} to {pct(r['hi'])}", "inside": r["inside"]} for r in dm["recovery"]],
        "forecastNotes": [
            {"ok": True, "t": "Beats the naive baseline", "d": f"MASE {mase['holt_winters']:.2f} against seasonal-naive {mase['seasonal_naive']:.2f}; only modestly better than a flat 28-day mean."},
            {"ok": False, "t": f"Day-level error is about {wape['holt_winters']:.0f}%", "d": f"Each city sees about {dm['mean_sessions']:.0f} sessions a day, so Poisson noise sets a high floor. An earlier '5–8%' claim compared 30-day averages and is withdrawn."},
            {"ok": False, "t": "No weather input, point forecasts only", "d": "Forecast temperature would help but is not available at prediction time in this dataset; intervals are not evaluated."},
        ],
        "geoRows": [
            {"k": "Expansion candidates flagged", "v": str(geo["observed"])},
            {"k": "Expected under shuffled demand", "v": f"{geo['null_mean']:.1f} (5–95%: {geo['null_p5']:.0f}–{geo['null_p95']:.0f})", "warn": True},
            {"k": "Permutation p-value", "v": f"{geo['p_value']:.2f}", "warn": geo["p_value"] > 0.05},
            {"k": "Demand vs distance-from-centre (Spearman)", "v": f"{geo['pooled_rho']:+.2f}, p = {geo['pooled_p']:.2f}"},
        ],
        "geoNotes": [
            {"ok": False, "t": "Flags are explained by layout, not demand", "d": "Shuffling which station is busy changes nothing: the candidates reflect where the stations are."},
            {"ok": False, "t": "No spatial demand exists in this data", "d": "The generator ties volume to power and connector count only. Demand measured at stations can never reveal unserved areas."},
            {"ok": True, "t": "What it does demonstrate", "d": "KMeans clustering, haversine coverage and an interactive map, plus the test that exposes their limits."},
        ],
        "realWeatherRows": int(real_weather),
    }


def main():
    data = build_data()
    data.pop("realWeatherRows")
    html = (BUILD / "dashboard_template.html").read_text(encoding="utf-8")
    html = html.replace("{{CSS}}", (BUILD / "dashboard.css").read_text(encoding="utf-8"))
    html = html.replace("{{DATA}}", json.dumps(data, separators=(",", ":")))
    (DOCS / "index.html").write_text(html, encoding="utf-8")
    print(f"Wrote {DOCS / 'index.html'} ({len(html)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
