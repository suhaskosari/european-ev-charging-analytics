# Sample Insights

Generated output from a full pipeline run on the synthetic 2024-2025 dataset
(seeded/deterministic -- re-running `python python/generate_data.py` end to
end reproduces these exact figures). Real numbers pulled directly from
`warehouse.duckdb` and `outputs/*.csv`, not illustrative placeholders.

## Headline metrics

- **49,042** clean charging sessions across **80** stations in **8** European
  cities (Stockholm, Oslo, Copenhagen, Berlin, Amsterdam, Paris, Madrid, Warsaw).
- **809,381 kWh** delivered, **€339,021** in session revenue over the 2-year window.
- Station utilization (share of connector-hours actually in use) ranges
  **0.7%-1.1%** by city -- Berlin and Amsterdam the busiest, Paris and Warsaw
  the least utilized relative to their station count, i.e. the two most
  over-provisioned networks in this dataset.

## What actually drives daily charging demand

`python/stats_demand_drivers.py` fits an OLS regression of daily
city-level session counts against temperature, precipitation, traffic
congestion and weekday/weekend:

| Driver | Coefficient | p-value | Significant? |
|---|---|---|---|
| Temperature (°C) | **-0.047** | < 0.001 | Yes |
| Precipitation (mm) | +0.016 | 0.134 | No |
| Traffic congestion index | **+0.021** | < 0.001 | Yes |
| Weekend | **-1.84** | < 0.001 | Yes |

Reading the significant coefficients: each **1°C drop** in average daily
temperature is associated with **~0.047 more sessions/day** per city (cold
weather reduces EV range, so drivers charge more often) -- and weekends see
**~1.84 fewer sessions/day** than weekdays, consistent with commute-driven
charging. Precipitation alone isn't a significant independent driver once
temperature and weekday are already in the model. This is the actual
data-generating relationship built into `generate_data.py`, and the
regression recovers it correctly -- a sanity check that the statistics layer
works, not just a plausible-looking number.

## 30-day demand forecast

`python/forecasting.py` fits a per-city Holt-Winters model (weekly
seasonality) on the full session history and forecasts 30 days forward.
Paris and Oslo forecast the highest sustained daily session volume; forecast
values track the trailing 30-day actuals closely (within ~5-8%) across all 8
cities, which is expected given the underlying series has no regime change
in the forecast window. See `outputs/charging_demand_forecast.png` for the
7-day-rolling-actual + forecast chart on the two busiest cities.

## Geospatial: where to add capacity

`python/geospatial_analysis.py` clusters session-volume-weighted station
coordinates per city and flags any cluster centroid more than 3km from the
nearest existing station. On this dataset, **Amsterdam** is the only city
with flagged expansion candidates -- two demand hotspots 3.2km and 4.0km from
the nearest existing charger, meaning the current Amsterdam network isn't
covering the geographic spread of its actual demand as tightly as the other
7 cities. Open `outputs/station_map.html` for the interactive map (blue
circles sized by session volume = existing stations, red pins = flagged
expansion sites).

## Data quality

`outputs/data_quality_report.md` (regenerated on every `etl_clean_transform.py`
run) logs every fix applied: duplicate-row removal, mixed-timestamp parsing,
sign-error correction, and missing-value imputation counts -- see
[docs/architecture.md](architecture.md#data-quality-issues-deliberately-injected-and-how-theyre-caught)
for the full list of deliberately injected issues and where each is caught.
