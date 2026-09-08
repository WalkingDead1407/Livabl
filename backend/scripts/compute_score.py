import json
import logging
from typing import Dict, List
import geopandas as gpd
from app.scoring.engine import ScoringEngine

logger = logging.getLogger(__name__)

def compute_ward_scores(
    wards_geojson_path: str,
    hospitals_geojson_path: str,
    schools_geojson_path: str,
    aqi_data_path: str,
    output_path: str
) -> List[Dict]:
    engine = ScoringEngine()
    wards = gpd.read_file(wards_geojson_path)
    hospitals = gpd.read_file(hospitals_geojson_path)
    schools = gpd.read_file(schools_geojson_path)
    with open(aqi_data_path, 'r') as f:
        aqi_data = json.load(f)

    results = []
    for idx, ward in wards.iterrows():
        ward_name = ward['ward_name'] or ward['name']
        healthcare_score = ward.get('hospital_score', 50)
        education_score = ward.get('school_score', 50)
        connectivity_score = ward.get('metro_score', 50)
        civic_score = ward.get('civic_score', 50)
        sentiment_score = ward.get('sentiment_score', 50)
        aqi_value = aqi_data.get(ward_name, None)
        score_result = engine.calculate_ward_score(
            ward_name=ward_name,
            healthcare_score=healthcare_score,
            education_score=education_score,
            connectivity_score=connectivity_score,
            aqi_value=aqi_value,
            civic_score=civic_score,
            sentiment_score=sentiment_score
        )
        ward_with_score = {
            **ward.to_dict(),
            'quality_score': score_result['final_score'],
            'quality_score_breakdown': score_result['breakdown'],
            'livability_class': score_result['classification']
        }
        results.append(ward_with_score)        
        logger.info(f"{ward_name}: {score_result['final_score']}/100")
    results_gdf = gpd.GeoDataFrame(results, crs=wards.crs)
    results_gdf.to_file(output_path, driver='GeoJSON')
    logger.info(f"Saved scores to {output_path}")
    return results


if __name__ == '__main__':
    compute_ward_scores(
        WARDS_GEOJSON,
        HOSPITALS_GEOJSON,
        SCHOOLS_GEOJSON,
        AQI_DATA,
        OUTPUT_PATH
    )
