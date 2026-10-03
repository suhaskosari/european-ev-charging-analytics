"""Warehouse integrity and analysis-validation checks (skipped if the pipeline has not been run)."""
import json
import sys
from pathlib import Path

import duckdb
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "python"))

DB = ROOT / "warehouse.duckdb"
OUT = ROOT / "outputs"
needs_db = pytest.mark.skipif(not DB.exists(), reason="warehouse not built")


@pytest.fixture(scope="module")
def con():
    c = duckdb.connect(str(DB), read_only=True)
    yield c
    c.close()


@needs_db
def test_sessions_inside_observation_window(con):
    lo, hi = con.execute("select min(start_time), max(start_time) from main_marts.fct_charging_sessions").fetchone()
    assert pd.Timestamp(lo) >= pd.Timestamp("2024-01-01") and pd.Timestamp(hi) < pd.Timestamp("2026-01-01")


@needs_db
def test_session_ids_unique_and_values_valid(con):
    n, d, neg_cost, bad_energy = con.execute("""
        select count(*), count(distinct session_id), sum(cost_eur < 0), sum(energy_kwh <= 0 or energy_kwh is null)
        from main_marts.fct_charging_sessions""").fetchone()
    assert n == d and neg_cost == 0 and bad_energy == 0


@needs_db
def test_every_session_has_a_station(con):
    orphans = con.execute("""
        select count(*) from main_marts.fct_charging_sessions s
        left join main_marts.dim_station d using (station_id) where d.station_id is null""").fetchone()[0]
    assert orphans == 0


@needs_db
def test_one_demand_row_per_city_day(con):
    n, d = con.execute("select count(*), count(distinct (city_key, date)) from main_analytics.city_daily_demand").fetchone()
    assert n == d


def test_haversine_stockholm_oslo():
    import geospatial_analysis as ga
    assert 410 < float(ga.haversine_km(59.3293, 18.0686, 59.9139, 10.7522)) < 425


@pytest.mark.skipif(not (OUT / "demand_model_validation.json").exists(), reason="validation not run")
def test_corrected_demand_model_recovers_most_true_parameters():
    v = json.loads((OUT / "demand_model_validation.json").read_text())
    assert v["n_inside"] >= 3
    assert 0.8 < v["dispersion"] < 1.3  # Poisson variance adequate


@pytest.mark.skipif(not (OUT / "forecast_backtest_detail.csv").exists(), reason="backtest not run")
def test_holt_winters_beats_seasonal_naive_in_backtest():
    r = pd.read_csv(OUT / "forecast_backtest_detail.csv")
    wape = r.groupby("model").apply(lambda g: g["abs_err"].sum() / g["actual_sum"].sum())
    assert wape["holt_winters"] < wape["seasonal_naive"]
