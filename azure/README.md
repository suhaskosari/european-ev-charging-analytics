# Azure / Microsoft Fabric Production Architecture

This repo runs entirely locally (Python + DuckDB + dbt) so anyone can clone
it and execute the full pipeline with zero cloud infrastructure or cost --
see the [root README](../README.md) for the local quickstart. This folder
documents how the **same pipeline** is designed to run in production on
Azure/Microsoft Fabric, and holds the actual pipeline/notebook definitions
(not deployed, since that requires a paid subscription) so the design is
concrete rather than a diagram-only claim.

## Mapping: local demo -> production

| Local demo (this repo)                              | Production (Azure / Fabric)                                            |
|-------------------------------------------------------|--------------------------------------------------------------------------|
| `python/fetch_*.py` REST pulls                          | **Azure Data Factory** Copy Data activities hitting the same REST APIs, landing raw JSON in the Bronze zone |
| `data/raw/*.csv`                                          | **ADLS Gen2** Bronze container (`bronze/ev/{source}/{yyyy}/{mm}/{dd}/`), partitioned by ingestion date |
| `python/etl_clean_transform.py`                             | **Fabric Lakehouse notebook** (PySpark, see `fabric/lakehouse_notebook.py`) writing cleaned Delta tables to the Silver zone |
| `python/load_warehouse.py` + `dbt run`                        | **dbt** running against **Fabric Warehouse** (or Synapse/Azure SQL) via `dbt-fabric`/`dbt-synapse`, materializing the Gold star schema |
| `warehouse.duckdb`                                              | **Fabric Warehouse** / **Azure Synapse dedicated SQL pool** |
| `sql/schema.sql`                                                  | Deployed via a dbt `on-run-start` migration or a dedicated IaC/Flyway step against the Fabric Warehouse |
| Manual script sequencing                                            | **ADF pipeline** (`adf/pipeline_ev_ingestion.json`) with a tumbling-window trigger, activity dependencies, and retry policies |
| `outputs/*.png` / `*.csv`                                             | Power BI **Direct Lake** mode over the Fabric Warehouse Gold tables -- no import refresh needed |

## Bronze / Silver / Gold zones

```
ADLS Gen2 (ev-datalake)
├── bronze/
│   ├── charging_stations/    (raw Open Charge Map JSON, source-system dump)
│   ├── weather/              (raw Open-Meteo JSON)
│   ├── charging_sessions/    (raw CPO billing exports, mixed formats)
│   ├── ev_registrations/     (national vehicle-registration authority exports)
│   ├── energy_prices/        (ENTSO-E Transparency Platform day-ahead prices)
│   └── traffic/              (traffic-authority congestion feeds)
├── silver/                   (cleaned, deduped, typed Delta tables -- one per bronze source)
└── gold/                     (dbt-modeled star schema: dim_*, fct_*, analytics marts)
```

Bronze is an untouched landing zone (auditability: replay any historical
load exactly as received). Silver is where `etl_clean_transform.py`'s logic
runs at Spark scale in Fabric -- dedup, timestamp normalization, sign-error
correction, missing-value imputation. Gold is the dbt-modeled warehouse this
repo's `dbt/ev_analytics/models/marts` already defines; only the compute
engine changes (DuckDB locally vs. Fabric Warehouse in production).

## Why this design, not a real deployment

Provisioning Data Factory, a Fabric capacity, and ADLS Gen2 costs money and
requires an Azure subscription with billing enabled -- not something to spin
up unattended for a portfolio demo. Instead, `adf/pipeline_ev_ingestion.json`
is a real, valid ADF pipeline definition (importable into an actual Data
Factory via **Author -> Import pipeline**) and `fabric/lakehouse_notebook.py`
is real, runnable PySpark (drop it into a Fabric or Databricks notebook cell
against a Lakehouse with the bronze paths mounted) -- both documented as
code, not just prose.
