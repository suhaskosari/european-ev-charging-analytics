"""
Shared constants used across the pipeline: the 8-city/8-country European
footprint the platform covers, and the analysis window.
"""
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
RAW_DIR = BASE / "data" / "raw"
PROCESSED_DIR = BASE / "data" / "processed"
OUT_DIR = BASE / "outputs"
DB_PATH = BASE / "warehouse.duckdb"

for d in (RAW_DIR, PROCESSED_DIR, OUT_DIR):
    d.mkdir(parents=True, exist_ok=True)

START_DATE = "2024-01-01"
END_DATE = "2025-12-31"

# city_key -> (display name, country, country_code, lat, lon, population_millions, region)
CITIES = {
    "stockholm":  ("Stockholm",  "Sweden",       "SE", 59.3293, 18.0686, 1.6,  "Nordics"),
    "oslo":       ("Oslo",       "Norway",       "NO", 59.9139, 10.7522, 1.0,  "Nordics"),
    "copenhagen": ("Copenhagen", "Denmark",      "DK", 55.6761, 12.5683, 0.8,  "Nordics"),
    "berlin":     ("Berlin",     "Germany",      "DE", 52.5200, 13.4050, 3.7,  "Western Europe"),
    "amsterdam":  ("Amsterdam",  "Netherlands",  "NL", 52.3676, 4.9041,  0.9,  "Western Europe"),
    "paris":      ("Paris",      "France",       "FR", 48.8566, 2.3522,  2.1,  "Western Europe"),
    "madrid":     ("Madrid",     "Spain",        "ES", 40.4168, -3.7038, 3.3,  "Southern Europe"),
    "warsaw":     ("Warsaw",     "Poland",       "PL", 52.2297, 21.0122, 1.9,  "Eastern Europe"),
}

CONNECTOR_TYPES = ["Type 2", "CCS", "CHAdeMO"]
