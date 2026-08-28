import logging
import os
import time
from typing import Optional

import geopandas as gpd
import osmnx as ox
from shapely.geometry import Point

from app.scoring.metrics import calculate_landfill_penalty, normalize_landfill_score

logger = logging.getLogger(__name__)

_LANDFILL_CACHE_TTL_SECONDS = 24 * 60 * 60 
_landfill_cache: dict[str, tuple[float, "gpd.GeoDataFrame"]] = {}

# Ward boundaries essentially never change, so the city boundary polygon used to scope each OSM query is cached indefinitely (process lifetime)
_city_boundary_cache: dict[str, object] = {}
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_city_boundary(city: str):
    if city in _city_boundary_cache:
        return _city_boundary_cache[city]
    #all wards currently in the dataset are Delhi's
    wards_path = os.path.join(_BACKEND_DIR, "data", "processed", "wards_clean.geojson")
    wards = gpd.read_file(wards_path)
    boundary = wards.union_all()
    _city_boundary_cache[city] = boundary
    return boundary

def _fetch_landfills_from_osm(city: str) -> gpd.GeoDataFrame:
    boundary = _load_city_boundary(city)
    logger.info("Fetching landfill sites from OSM for city=%s", city)
    tags = {"landuse": "landfill"}
    return ox.features_from_polygon(boundary, tags)


def get_landfill_locations(city: str) -> Optional[gpd.GeoDataFrame]:
    #cached OSM landfill locations for `city`, refetching once the cache entry is older than _LANDFILL_CACHE_TTL_SECONDS
    cached = _landfill_cache.get(city)
    if cached is not None and (time.time() - cached[0]) < _LANDFILL_CACHE_TTL_SECONDS:
        return cached[1]

    try:
        gdf = _fetch_landfills_from_osm(city)
    except Exception:
        logger.exception("Failed to fetch landfill sites from OSM for city=%s", city)
        #serve a stale cache entry rather than fail the request outright, if it has one
        return cached[1] if cached is not None else None

    _landfill_cache[city] = (time.time(), gdf)
    return gdf


def nearest_landfill_distance_km(lat: float, lng: float, city: str = "Delhi") -> Optional[float]:
    landfills = get_landfill_locations(city)
    if landfills is None or len(landfills) == 0:
        return None
    point = gpd.GeoSeries([Point(lng, lat)], crs=4326).to_crs(epsg=3857).iloc[0]
    dists_m = landfills.to_crs(epsg=3857).distance(point)
    return float(dists_m.min() / 1000) if len(dists_m) else None


def get_landfill_metrics(lat: float, lng: float, city: str = "Delhi") -> dict:
    distance_km = nearest_landfill_distance_km(lat, lng, city)
    return {
        "distance_km": distance_km,
        "penalty": calculate_landfill_penalty(distance_km),
        "landfill_score": normalize_landfill_score(distance_km),
    }
