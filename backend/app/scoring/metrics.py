from typing import Optional


def calculate_landfill_penalty(distance_km: Optional[float]) -> float:
    #penalty (higher = worse) for proximity to the nearest landfill
    if distance_km is None:
        return 0.0
    if distance_km < 1:
        return 40.0
    if distance_km < 2:
        return 30.0
    if distance_km < 5:
        return 20.0
    if distance_km < 10:
        return 10.0
    return 0.0


def normalize_landfill_score(distance_km: Optional[float]) -> Optional[float]:
    #higher = better/farther
    if distance_km is None:
        return None
    distance_km = min(distance_km, 10)
    return distance_km / 10


def calculate_environment_score(
    pollution_score: Optional[float], distance_km: Optional[float]) -> float:
    #Combine AQI-derived pollution_score (0-1) with landfill proximity into a single 0-1 environment score.
    base = pollution_score if pollution_score is not None else 0.0
    penalty = calculate_landfill_penalty(distance_km) / 100.0  # 0-0.4
    return max(0.0, min(1.0, base - penalty))
