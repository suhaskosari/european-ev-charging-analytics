#!/bin/sh
# End-to-end run: ingest -> clean -> warehouse -> dbt -> analysis -> validation -> docs -> tests
set -e
export DBT_PROFILES_DIR=dbt
[ -f dbt/profiles.yml ] || cp dbt/profiles.yml.example dbt/profiles.yml

python python/fetch_charging_stations.py
python python/fetch_weather_data.py
python python/generate_data.py
python python/etl_clean_transform.py
python python/load_warehouse.py

dbt run  --project-dir dbt/ev_analytics
dbt test --project-dir dbt/ev_analytics

python python/stats_demand_drivers.py
python python/forecasting.py
python python/geospatial_analysis.py
python python/export_for_powerbi.py

for step in eval_demand_model eval_forecast eval_geospatial write_sample_insights build_dashboard; do
  [ -f python/$step.py ] && python python/$step.py
done
pytest -q
