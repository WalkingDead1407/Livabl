import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import geopandas as gpd
from app.services.landfill_service import get_landfill_locations
from app.scoring.metrics import calculate_landfill_penalty, normalize_landfill_score

PATH = ROOT / "data" / "processed" / "wards_score.geojson"
UTM = 32643  # metres, accurate for Delhi
wards = gpd.read_file(PATH)
landfills = get_landfill_locations("Delhi")
if landfills is None or landfills.empty:
    raise SystemExit("No landfill data fetched from OSM")

landfill_union = landfills.to_crs(UTM).union_all()
centroids = wards.to_crs(UTM).geometry.centroid

wards["landfill_distance_km"] = centroids.distance(landfill_union) / 1000
wards["landfill_penalty"] = wards["landfill_distance_km"].apply(calculate_landfill_penalty)
wards["landfill_score"] = wards["landfill_distance_km"].apply(normalize_landfill_score)

wards.to_file(PATH, driver="GeoJSON")
print(wards[["Ward_Name", "landfill_distance_km", "landfill_penalty"]].sort_values("landfill_distance_km").head(10))
