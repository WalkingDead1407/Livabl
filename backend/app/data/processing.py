import logging
from socket import TCP_FASTOPEN_CONNECT
from typing import Dict, List, Any, Optional

try:
    from app.data.schemas import WardScore, Ward
except ImportError:
    from schemas import WardScore, Ward

# api import
try:
    from realtime_aqi import WAQIClient
    from aqi_cache import AQICache
    from aqi_config import AQIConfig
    aqi_client = WAQIClient()
    aqi_cache = AQICache()
except ImportError:
    aqi_client = None
    aqi_cache = None

logger = logging.getLogger(__name__)
class ProcessingError(Exception):
    pass


def get_realtime_pollution_score(lat: float, lon: float) -> Optional[float]:
    if not aqi_client:
        return None

    try:
        cache_key = f"{lat}_{lon}"
        cached = aqi_cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit for {lat},{lon}: {cached}")
            return cached

        aqi = aqi_client.get_aqi_by_coordinates(lat, lon)

        if aqi is not None:
            aqi_cache.set(cache_key, aqi)
            logger.info(f"Real-time AQI for {lat},{lon}: {aqi:.1f}/100")
            return aqi

        return None

    except Exception as e:
        logger.error(f"Error getting real-time AQI: {e}")
        return None

def parse_features(geojson_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    try:
        logger.info("Parsing features from GeoJSON...")

        if not isinstance(geojson_data, dict):
            raise ProcessingError("Input must be a dictionary")
        if "features" not in geojson_data:
            raise ProcessingError("GeoJSON does not contain 'features' array")
        features = geojson_data["features"]
        if not isinstance(features, list):
            raise ProcessingError(f"'features' must be an array, got {type(features)}")
        if len(features) == 0:
            logger.warning("GeoJSON has empty features array")
        logger.info(f"✓ Parsed {len(features)} features from GeoJSON")
        return features
 
    except ProcessingError:
        raise
    except Exception as e:
        logger.error(f"Error parsing features: {e}")
        raise ProcessingError(f"Failed to parse features: {e}") from e

def validate_features(features: List[Dict[str, Any]]) -> Dict[str, Any]:
    valid_count = 0
    invalid_count = 0
    errors = []
    logger.info(f"Validating {len(features)} features...")
    for i, feature in enumerate(features):
        try:
            if not isinstance(feature, dict):
                errors.append(f"Feature {i}: Not a dictionary")
                invalid_count += 1
                continue

            if feature.get("type") != "Feature":
                errors.append(f"Feature {i}: Invalid type '{feature.get('type')}'")
                invalid_count += 1
                continue

            if "properties" not in feature:
                errors.append(f"Feature {i}: Missing 'properties'")
                invalid_count += 1
                continue

            if "geometry" not in feature:
                errors.append(f"Feature {i}: Missing 'geometry'")
                invalid_count += 1
                continue
            valid_count += 1
        except Exception as e:
            errors.append(f"Feature {i}: {str(e)}")
            invalid_count += 1
    result = {
        "total_count": len(features),
        "valid_count": valid_count,
        "invalid_count": invalid_count,
        "errors": errors[:10]
    }
    logger.info(f"Validation: {valid_count} valid, {invalid_count} invalid")
    return result

def filter_valid_features(features: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    valid_features = []
    invalid_count = 0
    for i, feature in enumerate(features):
        try:
            if (isinstance(feature, dict) and
                feature.get("type") == "Feature" and
                "properties" in feature and
                "geometry" in feature):
                valid_features.append(feature)
            else:
                invalid_count += 1
        except Exception as e:
            logger.warning(f"Feature {i} validation failed: {e}")
            invalid_count += 1

    if invalid_count > 0:
        logger.info(f"Filtered out {invalid_count} invalid features")
    return valid_features

def get_feature_stats(features: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not features:
        return {
            "count": 0,
            "avg_properties": 0,
            "geometry_types": {}
        }
    total_properties = 0
    geometry_types = {}

    for feature in features:
        props = feature.get("properties", {})
        total_properties += len(props)
 
        geometry = feature.get("geometry", {})
        geom_type = geometry.get("type", "unknown")
        geometry_types[geom_type] = geometry_types.get(geom_type, 0) + 1

    return {
        "count": len(features),
        "avg_properties": round(total_properties / len(features), 2),
        "geometry_types": geometry_types,
        "total_properties": total_properties
    }

def parse_features_safe(geojson_data: Dict[str, Any], allow_empty: bool = True) -> List[Dict[str, Any]]:
    try:
        logger.info("Starting safe feature parsing...")
        features = parse_features(geojson_data)
        if not features and not allow_empty:
            raise ProcessingError("Feature list is empty")
        valid_features = filter_valid_features(features)

        if not valid_features and features:
            logger.warning("All features were invalid after filtering")
        logger.info(f"Safe parse complete: {len(valid_features)} valid features")
        return valid_features

    except ProcessingError:
        raise
    except Exception as e:
        logger.error(f"Safe parse failed: {e}")
        raise ProcessingError(f"Failed to parse features safely: {e}") from e


def normalize_score(value: Any) -> Optional[float]:
    if value is None:
        return None

    try:
        score = float(value)
        if 0 <= score <= 1:
            normalized = score * 100
        else:
            normalized = max(0, min(100, score))

        return round(normalized, 2)
    except (ValueError, TypeError):
        logger.warning(f"Cannot convert '{value}' to float, returning None")
        return None

def extract_metric_breakdown(properties: Dict[str, Any], geometry: Dict[str, Any] = None) -> WardScore:
    overall_score = normalize_score(properties.get("livability_score"))
    if overall_score is None:
        raise ProcessingError("Feature missing required 'livability_score' field")
    environment_score = None
    if geometry:
        try:
            coords = geometry.get("coordinates", [])
            if coords and geometry.get("type") == "Polygon":
                #centroid of polygon (average of coordinates)
                polygon_coords = coords[0]
                lats = [c[1] for c in polygon_coords]
                lons = [c[0] for c in polygon_coords]
                lat = sum(lats) / len(lats)
                lon = sum(lons) / len(lons)
                realtime_aqi = get_realtime_pollution_score(lat, lon)
                if realtime_aqi is not None:
                    environment_score = realtime_aqi
        except Exception as e:
            logger.debug(f"Could not extract coordinates for real-time AQI: {e}")
 
    # fallback to static pollution_score if real-time unavailable
    if environment_score is None:
        environment_score = normalize_score(properties.get("pollution_score"))
    landfill_penalty = properties.get("landfill_penalty")
    if environment_score is not None and landfill_penalty is not None:
        environment_score = max(0.0, environment_score - float(landfill_penalty))
    return WardScore(
        overall_score=overall_score,
        healthcare_access=normalize_score(properties.get("hospital_score")),
        education_access=normalize_score(properties.get("school_score")),
        environment=environment_score,  # Real-time or static
    )

def extract_ward_features(feature: Dict[str, Any]) -> Ward:
    try:
        properties = feature.get("properties", {})
        ward_id = properties.get("ward_id")
        if ward_id is None:
            raise ProcessingError("Feature missing 'ward_id' in properties")
        name = properties.get("Ward_Name")
        if not name:
            raise ProcessingError(f"Feature {ward_id} missing 'Ward_Name' in properties")

        geometry = feature.get("geometry")
        if not geometry:
            raise ProcessingError(f"Feature {ward_id} missing 'geometry'")

        logger.debug(f"Extracting metrics for ward: {ward_id} - {name}")
        scores = extract_metric_breakdown(properties, geometry)  #geometry for real-time AQI

        ward = Ward(
            id=str(ward_id),
            name=str(name),
            scores=scores,
            geometry=geometry
        )

        logger.debug(f"Extracted ward: {ward_id} - {name} (Score: {scores.overall_score})")
        return ward

    except ProcessingError:
        raise
    except Exception as e:
        logger.error(f"Error extracting feature: {e}")
        raise ProcessingError(f"Failed to extract feature: {e}") from e

def transform_features_to_wards(features: List[Dict[str, Any]]) -> List[Ward]:
    wards = []
    skipped = 0
    logger.info(f"Transforming {len(features)} features to Ward objects...")

    for i, feature in enumerate(features):
        try:
            ward = extract_ward_features(feature)
            wards.append(ward)
        except ProcessingError as e:
            skipped += 1
            if skipped <= 3:
                logger.warning(f"Skipped feature {i}: {e}")
    if skipped > 0:
        logger.info(f"Transformed {len(wards)} features ({skipped} skipped)")
    else:
        logger.info(f"Transformed {len(wards)} features (all valid)")
    return wards

def validate_ward_data(ward: Ward) -> Dict[str, Any]:
    issues = []

    if not ward.id or not isinstance(ward.id, str):
        issues.append("Invalid or missing ID")

    if not ward.name or not isinstance(ward.name, str):
        issues.append("Invalid or missing name")

    if ward.scores.overall_score is None:
        issues.append("Missing overall score")

    if not ward.geometry or not ward.geometry.get("type"):
        issues.append("Invalid or missing geometry")

    return {
        "is_valid": len(issues) == 0,
        "issues": issues
    }

try:
    from schemas import Ward
except ImportError:
    pass
logger = logging.getLogger(__name__)

def get_all_wards(geojson_data: Dict[str, Any]) -> List[Ward]:
    try:
        logger.info("Getting all wards...")
        features = parse_features(geojson_data)

        if not features:
            logger.warning("No features found in GeoJSON")
            return []

        wards = transform_features_to_wards(features)
        if not wards:
            raise ProcessingError("No valid wards found in dataset")
        logger.info(f"Retrieved {len(wards)} wards")
        return wards

    except ProcessingError:
        raise
    except Exception as e:
        logger.error(f"Error getting all wards: {e}")
        raise ProcessingError(f"Failed to get all wards: {e}") from e
def get_ward_by_id(geojson_data: Dict[str, Any], ward_id: Any) -> Ward:
    try:
        logger.info(f"Getting ward by ID: {ward_id}")
        features = parse_features(geojson_data)
        try:
            ward_id_to_find = int(ward_id)
        except (ValueError, TypeError):
            ward_id_to_find = ward_id

        for feature in features:
            feature_ward_id = feature.get("properties", {}).get("ward_id")
            if feature_ward_id is not None:
                try:
                    if int(feature_ward_id) == int(ward_id_to_find):
                        ward = extract_ward_features(feature)
                        logger.info(f"Found ward: {ward.name}")
                        return ward
                except (ValueError, TypeError):
                    continue
    except ProcessingError:
        raise
    except Exception as e:
        logger.error(f"Error getting ward {ward_id}: {e}")
        raise ProcessingError(f"Failed to get ward {ward_id}: {e}") from e
def get_wards_by_ids(geojson_data: Dict[str, Any], ward_ids: List[str]) -> List[Ward]:
    wards = []
    not_found = []
    logger.info(f"Getting {len(ward_ids)} wards by ID...")

    for ward_id in ward_ids:
        try:
            ward = get_ward_by_id(geojson_data, ward_id)
            wards.append(ward)
        except ProcessingError:
            not_found.append(ward_id)
    if not_found:
        logger.warning(f"Wards not found: {not_found}")

    logger.info(f"Retrieved {len(wards)} out of {len(ward_ids)} requested wards")
    return wards 
def compare_wards(wards: List[Ward]) -> Dict[str, Any]:
    if not wards:
        raise ProcessingError("Cannot compare empty ward list")
    if len(wards) < 2:
        logger.warning("Comparing less than 2 wards - may not be meaningful")
    logger.info(f"Comparing {len(wards)} wards...")
    sorted_wards = sorted(
        wards,
        key=lambda w: w.scores.overall_score,
        reverse=True
    )
    avg_score = sum(w.scores.overall_score for w in wards) / len(wards)

    comparison = {
        "wards": [w.model_dump() for w in wards],
        "sorted_by_score": [w.model_dump() for w in sorted_wards],
        "best_ward": sorted_wards[0].model_dump(),
        "worst_ward": sorted_wards[-1].model_dump(),
        "average_score": round(avg_score, 2),
        "score_range": {
            "max": sorted_wards[0].scores.overall_score,
            "min": sorted_wards[-1].scores.overall_score,
            "difference": round(
                sorted_wards[0].scores.overall_score - sorted_wards[-1].scores.overall_score,
                2
            )
        }
    }

    logger.info(f"Comparison complete. Best: {sorted_wards[0].name}, "f"Worst: {sorted_wards[-1].name}, Avg: {avg_score:.2f}") 
    return comparison
def filter_wards_by_score( wards: List[Ward], min_score: float = 0, max_score: float = 100) -> List[Ward]:
    min_score = max(0, min(100, min_score))
    max_score = max(0, min(100, max_score))
    if min_score > max_score:
        logger.warning(f"min_score {min_score} > max_score {max_score}, swapping")
        min_score, max_score = max_score, min_score

    filtered = [
        w for w in wards
        if min_score <= w.scores.overall_score <= max_score
    ]

    logger.info(
        f"Filtered {len(wards)} wards to {len(filtered)} "
        f"in range [{min_score}, {max_score}]"
    )
    return filtered

def sort_wards(wards: List[Ward],sort_by: str = "overall_score",reverse: bool = True) -> List[Ward]:
        try:
            logger.info(f"Sorting {len(wards)} wards by {sort_by}...")
            if sort_by == "overall_score":
                return sorted(
                    wards,
                    key=lambda w: w.scores.overall_score,
                    reverse=reverse
                )
            elif sort_by == "name":
                return sorted(wards, key=lambda w: w.name, reverse=reverse)
            elif sort_by == "healthcare_access":
                return sorted(
                    wards,
                    key=lambda w: w.scores.healthcare_access or 0,
                    reverse=reverse
                )
            elif sort_by == "education_access":
                return sorted(
                    wards,
                    key=lambda w: w.scores.education_access or 0,
                    reverse=reverse
                )
            elif sort_by == "environment":
                return sorted(
                    wards,
                    key=lambda w: w.scores.environment or 0,
                    reverse=reverse
                )
            elif sort_by == "connectivity":
                return sorted(
                    wards,
                    key=lambda w: w.scores.connectivity or 0,
                    reverse=reverse
                )
            else:
                logger.warning(f"Unknown sort field: {sort_by}, returning unsorted")
                return wards
        except Exception as e:
            logger.error(f"Error sorting wards: {e}")
            return wards
 
def get_ward_statistics(wards: List[Ward]) -> Dict[str, Any]:
    if not wards:
        logger.warning("No wards provided for statistics")
        return {
            "count": 0,
            "average_score": 0,
            "median_score": 0,
            "min_score": 0,
            "max_score": 0,
            "std_dev": 0
        }
    logger.info(f"Calculating statistics for {len(wards)} wards...")
    scores = [w.scores.overall_score for w in wards]
    sorted_scores = sorted(scores)
    n = len(sorted_scores)
    if n % 2 == 1:
        median = sorted_scores[n // 2]
    else:
        median = (sorted_scores[n // 2 - 1] + sorted_scores[n // 2]) / 2
    avg = sum(scores) / len(scores)

    if len(scores) > 1:
        variance = sum((x - avg) ** 2 for x in scores) / len(scores)
        std_dev = variance ** 0.5
    else:
        std_dev = 0
    stats = {
        "count": len(wards),
        "average_score": round(avg, 2),
        "median_score": round(median, 2),
        "min_score": min(scores),
        "max_score": max(scores),
        "std_dev": round(std_dev, 2),
        "total_score_sum": round(sum(scores), 2)
    }

    logger.info(
        f"Statistics: Avg={stats['average_score']}, "
        f"Median={stats['median_score']}, StdDev={stats['std_dev']}"
    )

    return stats

def get_top_wards(wards: List[Ward], n: int = 10) -> List[Ward]:
    sorted_wards = sort_wards(wards, "overall_score", reverse=True)
    top_n = sorted_wards[:n]
    logger.info(f"Retrieved top {len(top_n)} wards")
    return top_n

def get_bottom_wards(wards: List[Ward], n: int = 10) -> List[Ward]:
    sorted_wards = sort_wards(wards, "overall_score", reverse=False)
    bottom_n = sorted_wards[:n]
    logger.info(f"Retrieved bottom {len(bottom_n)} wards")
    return bottom_n
 
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        from ingestion import load_geojson
        print("Step 1: Loading GeoJSON data...")
        data = load_geojson("wards_score.geojson")
        print(f"Loaded {len(data['features'])} features")
        print("\nStep 2: Parsing features...")
        features = parse_features(data)
        print(f"Parsed {len(features)} features")
        print("\nStep 3: Validating features...")
        validation = validate_features(features)
        print(f"Valid: {validation['valid_count']}, Invalid: {validation['invalid_count']}")
        print("\nStep 4: Transforming to Ward objects...")
        wards = transform_features_to_wards(features)
        print(f"Transformed {len(wards)} wards")

        if wards:
            ward = wards[0]
            print(f"\nSample Ward:")
            print(f"ID: {ward.id}")
            print(f"Name: {ward.name}")
            print(f"Livability Score: {ward.scores.overall_score}/100")
            print(f"Hospital Score: {ward.scores.healthcare_access}/100")
            print(f"School Score: {ward.scores.education_access}/100")
            print(f"Pollution Score: {ward.scores.environment}/100")

        print("\nTest 1: Get all wards...")
        all_wards = get_all_wards(data)
        print(f"Got {len(all_wards)} wards")
        print("\nTest 2: Get single ward by ID...")
        single_ward = get_ward_by_id(data, "1")
        print(f"Got ward: {single_ward.name} (Score: {single_ward.scores.overall_score}/100)")
        print("\nTest 3: Get multiple wards by IDs...")
        multiple_wards = get_wards_by_ids(data, ["1", "2", "3"])
        print(f"Got {len(multiple_wards)} wards")
        print("\nTest 4: Compare wards...")
        comparison = compare_wards(multiple_wards)
        print(f"Best ward: {comparison['best_ward']['name']} ({comparison['best_ward']['scores']['overall_score']}/100)")
        print(f"Worst ward: {comparison['worst_ward']['name']} ({comparison['worst_ward']['scores']['overall_score']}/100)")
        print(f"Average score: {comparison['average_score']}/100")
        print(f"Score range: {comparison['score_range']['min']} - {comparison['score_range']['max']}")
        print("\nTest 5: Filter wards by score (min=70)...")
        filtered = filter_wards_by_score(all_wards, min_score=70)
        print(f"{len(filtered)} wards with score >= 70")
        print("\nTest 6: Sort wards by score (descending)...")
        sorted_wards = sort_wards(all_wards, "overall_score", reverse=True)
        print(f"Top 3 wards:")
        for i, w in enumerate(sorted_wards[:3], 1):
            print(f"  {i}. {w.name}: {w.scores.overall_score}/100")
        print("\nTest 7: Get ward statistics...")
        stats = get_ward_statistics(all_wards)
        print(f"Total wards: {stats['count']}")
        print(f"Average score: {stats['average_score']}/100")
        print(f"Median score: {stats['median_score']}/100")
        print(f"Min score: {stats['min_score']}/100")
        print(f"Max score: {stats['max_score']}/100")
        print(f"Std Dev: {stats['std_dev']}")
        print("\nTest 8: Get top 5 wards...")
        top_5 = get_top_wards(all_wards, 5)
        print(f"Top 5 wards:")
        for i, w in enumerate(top_5, 1):
            print(f"  {i}. {w.name}: {w.scores.overall_score}/100")
        print("\nTest 9: Get bottom 5 wards...")
        bottom_5 = get_bottom_wards(all_wards, 5)
        print(f"Bottom 5 wards:")
        for i, w in enumerate(bottom_5, 1):
            print(f"  {i}. {w.name}: {w.scores.overall_score}/100")
        print("ALL TESTS PASSED!")
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
