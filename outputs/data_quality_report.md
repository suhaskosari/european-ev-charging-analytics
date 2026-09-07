# Data Quality Report

_Generated 2026-09-07T23:40:37.487768+00:00_


## Stations

- Removed 2 duplicate station_id rows (82 -> 80).
- Normalized connector_type casing (e.g. 'chademo' -> 'CHAdeMO').

## Charging Sessions

- Removed 736 duplicate session_id rows (49,778 -> 49,042).
- Parsed 2 mixed timestamp formats (ISO + `dd/mm/yyyy HH:MM`); 0 unparseable rows dropped.
- Corrected 490 sign-error costs (billing refund coded as negative charge).
- Imputed 1471 missing energy_kwh readings from duration x rated power (not a flat mean fill).
- Dropped 0 rows with non-positive duration_min.

## Summary

- 80 clean stations across 8 cities.
- 49,042 clean charging sessions retained for the warehouse.