"""
Geospatial analytics layer: for each city, clusters observed charging demand
into hotspots (KMeans over station locations weighted by session volume),
then flags any hotspot whose nearest existing station is further than a
walkable/practical threshold away as an infrastructure-expansion candidate.

Distances use the haversine formula directly (no geopandas/GDAL dependency,
so the demo has no native-binary install requirement); coordinates and
clustering are still genuine geospatial analysis.

Writes a candidate-site CSV and an interactive Folium map.

Run (after `dbt run`):
    python python/geospatial_analysis.py
"""
import duckdb
import folium
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

from common import DB_PATH, OUT_DIR

EARTH_RADIUS_KM = 6371.0
EXPANSION_DISTANCE_THRESHOLD_KM = 3.0
STATIONS_PER_CLUSTER_TARGET = 4  # roughly one cluster per this many existing stations


def get_con():
    return duckdb.connect(str(DB_PATH), read_only=True)


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


def load_data(con):
    stations = con.execute("""
        select station_id, city_key, city_name, latitude, longitude
        from main_marts.dim_station
    """).df()
    demand = con.execute("""
        select station_id, sum(sessions_count) as total_sessions
        from main_analytics.station_utilization
        group by 1
    """).df()
    return stations.merge(demand, on="station_id", how="left").fillna({"total_sessions": 0})


def find_expansion_candidates(city_stations: pd.DataFrame) -> pd.DataFrame:
    n_stations = len(city_stations)
    n_clusters = max(n_stations // STATIONS_PER_CLUSTER_TARGET, 2)

    # weight each station's coordinates by its session volume so cluster
    # centroids drift toward genuinely busy areas, not just station density
    weights = (city_stations["total_sessions"] + 1).to_numpy()
    coords = city_stations[["latitude", "longitude"]].to_numpy()
    repeated = np.repeat(coords, np.ceil(weights / weights.min()).astype(int), axis=0)

    km = KMeans(n_clusters=n_clusters, n_init=10, random_state=42).fit(repeated)
    centroids = km.cluster_centers_

    rows = []
    for lat, lon in centroids:
        dists = haversine_km(lat, lon, city_stations["latitude"].to_numpy(), city_stations["longitude"].to_numpy())
        nearest_km = dists.min()
        rows.append({
            "city_key": city_stations["city_key"].iloc[0],
            "city_name": city_stations["city_name"].iloc[0],
            "candidate_latitude": round(float(lat), 5),
            "candidate_longitude": round(float(lon), 5),
            "nearest_existing_station_km": round(float(nearest_km), 2),
            "expansion_candidate": bool(nearest_km > EXPANSION_DISTANCE_THRESHOLD_KM),
        })
    return pd.DataFrame(rows)


def build_map(stations: pd.DataFrame, candidates: pd.DataFrame) -> folium.Map:
    center = [stations["latitude"].mean(), stations["longitude"].mean()]
    m = folium.Map(location=center, zoom_start=4, tiles="OpenStreetMap")

    for _, s in stations.iterrows():
        folium.CircleMarker(
            location=[s["latitude"], s["longitude"]],
            radius=3 + min(s["total_sessions"] / 40, 6),
            color="#3b6fa0", fill=True, fill_opacity=0.6,
            popup=f"{s['station_id']} ({s['city_name']}) - {int(s['total_sessions'])} sessions",
        ).add_to(m)

    for _, c in candidates[candidates["expansion_candidate"]].iterrows():
        folium.Marker(
            location=[c["candidate_latitude"], c["candidate_longitude"]],
            icon=folium.Icon(color="red", icon="bolt", prefix="fa"),
            popup=f"Expansion candidate: {c['city_name']} "
                  f"({c['nearest_existing_station_km']} km from nearest station)",
        ).add_to(m)

    return m


def main():
    con = get_con()
    stations = load_data(con)
    con.close()

    all_candidates = []
    for city_key, grp in stations.groupby("city_key"):
        candidates = find_expansion_candidates(grp.reset_index(drop=True))
        all_candidates.append(candidates)

    candidates = pd.concat(all_candidates, ignore_index=True)
    candidates.to_csv(OUT_DIR / "station_expansion_candidates.csv", index=False)
    n_flagged = candidates["expansion_candidate"].sum()
    print(f"Flagged {n_flagged}/{len(candidates)} demand-weighted cluster centroids as expansion "
          f"candidates (>{EXPANSION_DISTANCE_THRESHOLD_KM}km from the nearest existing station)")
    print(f"  -> outputs/station_expansion_candidates.csv")

    m = build_map(stations, candidates)
    m.save(str(OUT_DIR / "station_map.html"))
    print(f"  -> outputs/station_map.html (interactive map: existing stations + expansion candidates)")


if __name__ == "__main__":
    main()
