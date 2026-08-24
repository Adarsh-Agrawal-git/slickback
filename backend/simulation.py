from datetime import datetime, timedelta, timezone
import math
import numpy as np

# Prototype-only synthetic vessels. Real AIS will replace this later.
VESSELS = [
    {
        "mmsi": "419001001", "name": "VESSEL ALPHA", "lat": 18.7055, "lon": 73.00,
        "historical_lat": 18.70555, "historical_lon": 72.58747,
        "historical_hours_before": 6.0,
        "speed_knots": 12.0, "heading": 70.0, "ais_reliability": 0.96,
        "ais_gap_hours": 0.0, "sar_support": 0.72,
    },
    {
        "mmsi": "419001002", "name": "VESSEL BRAVO", "lat": 18.82, "lon": 72.70,
        "speed_knots": 14.0, "heading": 250.0, "ais_reliability": 0.93,
        "ais_gap_hours": 2.5, "sar_support": 0.61,
    },
    {
        "mmsi": "419001003", "name": "VESSEL CHARLIE", "lat": 18.55, "lon": 72.58,
        "speed_knots": 48.0, "heading": 90.0, "ais_reliability": 0.42,
        "ais_gap_hours": 0.0, "sar_support": 0.84,
    },
    {
        "mmsi": "419001004", "name": "VESSEL DELTA", "lat": 19.02, "lon": 72.35,
        "speed_knots": 11.0, "heading": 180.0, "ais_reliability": 0.98,
        "ais_gap_hours": 0.0, "sar_support": 0.25,
    },
]


def destination(lat, lon, bearing_deg, distance_km):
    """Approximate destination point for short maritime distances."""
    bearing = math.radians(bearing_deg)
    lat2 = lat + (distance_km * math.cos(bearing)) / 111.0
    lon_scale = max(math.cos(math.radians(lat)), 0.2)
    lon2 = lon + (distance_km * math.sin(bearing)) / (111.0 * lon_scale)
    return lat2, lon2


def backward_particles(lat, lon, hours_back, n=400):
    """Synthetic backward drift: wind/current field + uncertainty.
    This is intentionally not OpenDrift yet; it gives us a working prototype loop.
    """
    rng = np.random.default_rng(42)
    # Approximate environmental drift for demo purposes.
    current_speed_kmh = 1.2
    current_bearing = 55.0
    wind_speed_kmh = 7.0
    wind_bearing = 40.0

    total_dx = 0.0
    total_dy = 0.0
    for _ in range(hours_back):
        # Reverse the observed motion.
        total_dx -= current_speed_kmh * math.sin(math.radians(current_bearing))
        total_dy -= current_speed_kmh * math.cos(math.radians(current_bearing))
        total_dx -= 0.025 * wind_speed_kmh * math.sin(math.radians(wind_bearing))
        total_dy -= 0.025 * wind_speed_kmh * math.cos(math.radians(wind_bearing))

    sigma = max(0.7, hours_back * 0.18)
    dx = total_dx + rng.normal(0, sigma, n)
    dy = total_dy + rng.normal(0, sigma, n)

    lon_scale = max(math.cos(math.radians(lat)), 0.2)
    lats = lat + dy / 111.0
    lons = lon + dx / (111.0 * lon_scale)

    return lats, lons


def score_vessel(vessel, source_lat, source_lon, observation_time, hours_back):
    # For the adversarial Stage-1 scenario, Alpha has a known historical AIS
    # position at the reconstructed source 6 hours before observation.
    # The current position is intentionally far from the observed slick.
    historical_match = (
        "historical_lat" in vessel
        and abs(vessel.get("historical_hours_before", -999) - hours_back) < 0.5
    )
    eval_lat = vessel.get("historical_lat", vessel["lat"]) if historical_match else vessel["lat"]
    eval_lon = vessel.get("historical_lon", vessel["lon"]) if historical_match else vessel["lon"]

    dlat = (eval_lat - source_lat) * 111.0
    dlon = (eval_lon - source_lon) * 111.0 * math.cos(math.radians(source_lat))
    distance = math.sqrt(dlat * dlat + dlon * dlon)

    spatial = max(0.0, 100.0 * math.exp(-distance / 12.0))

    # Temporal compatibility is high when the historical position aligns with
    # the reconstructed release window.
    gap_penalty = min(vessel["ais_gap_hours"] / max(hours_back, 1), 1.0) * 25.0
    temporal = 97.0 if historical_match else max(0.0, 88.0 - gap_penalty)

    # Penalize physically implausible AIS speeds.
    speed_anomaly = max(0.0, min(1.0, (vessel["speed_knots"] - 25.0) / 30.0))
    kinematic = 100.0 * (1.0 - 0.45 * speed_anomaly)

    drift = max(0.0, 100.0 - distance * 3.0)
    ais_trust = vessel["ais_reliability"] * 100.0
    sar = vessel["sar_support"] * 100.0

    overall = (
        0.28 * spatial
        + 0.20 * temporal
        + 0.20 * drift
        + 0.17 * ais_trust
        + 0.10 * sar
        + 0.05 * kinematic
    )

    return {
        "mmsi": vessel["mmsi"],
        "name": vessel["name"],
        "distance_km": round(distance, 2),
        "evaluated_position": {"lat": round(eval_lat, 5), "lon": round(eval_lon, 5)},
        "historical_source_match": historical_match,
        "spatial_match": round(spatial, 1),
        "temporal_match": round(temporal, 1),
        "drift_match": round(drift, 1),
        "ais_trust": round(ais_trust, 1),
        "sar_support": round(sar, 1),
        "kinematic_score": round(kinematic, 1),
        "ais_gap_hours": vessel["ais_gap_hours"],
        "overall_score": round(overall, 1),
        "flags": [
            "AIS GAP" if vessel["ais_gap_hours"] > 0 else None,
            "KINEMATIC ANOMALY" if vessel["speed_knots"] > 25 else None,
            "HISTORICAL SOURCE MATCH" if historical_match else None,
        ],
    }


def generate_spill_analysis(lat, lon, observation_time, hours_back):
    lats, lons = backward_particles(lat, lon, hours_back)
    source_lat = float(np.mean(lats))
    source_lon = float(np.mean(lons))

    # Ellipse-like source uncertainty derived from particle spread.
    source_radius_km = float(max(np.std(lats), np.std(lons)) * 111.0 * 2.0)

    candidates = [
        score_vessel(v, source_lat, source_lon, observation_time, hours_back)
        for v in VESSELS
    ]
    candidates.sort(key=lambda x: x["overall_score"], reverse=True)

    # Strip null flags.
    for c in candidates:
        c["flags"] = [f for f in c["flags"] if f]

    source_time = observation_time - timedelta(hours=hours_back)

    return {
        "incident": {
            "observed_at": observation_time.isoformat(),
            "hours_rewound": hours_back,
            "slick": {
                "lat": lat,
                "lon": lon,
                "area_km2": 14.2,
                "detection_confidence": 87.0,
            },
        },
        "source_reconstruction": {
            "source_lat": round(source_lat, 5),
            "source_lon": round(source_lon, 5),
            "uncertainty_radius_km": round(source_radius_km, 2),
            "release_window_start": source_time.isoformat(),
            "release_window_end": (source_time + timedelta(hours=2)).isoformat(),
            "particle_count": len(lats),
        },
        "environment": {
            "current_speed_kmh": 1.2,
            "current_bearing_deg": 55,
            "wind_speed_kmh": 7.0,
            "wind_bearing_deg": 40,
            "provider": "SYNTHETIC PROTOTYPE DATA",
        },
        "lookalike_analysis": {
            "oil_probability": 77.0,
            "low_wind_probability": 12.0,
            "ship_wake_probability": 4.0,
            "biogenic_probability": 7.0,
            "status": "PROBABLE OIL",
        },
        "candidates": candidates,
        "scenario": {
            "name": "DRIFT-TIME-LAG ADVERSARIAL CASE",
            "purpose": "Baseline is expected to favor the nearest current vessel, while SlickBack evaluates historical vessel positions against the reconstructed source.",
        },
        "disclaimer": "Prototype ranking is an investigation lead, not legal proof of responsibility.",
    }


def baseline_distance_score(vessel, spill_lat, spill_lon):
    """Baseline attribution: rank vessels only by distance to observed slick.

    This is intentionally simple. It is our control/baseline against which
    the full SlickBack evidence-fusion pipeline will be compared.
    """
    dlat = (vessel["lat"] - spill_lat) * 111.0
    dlon = (vessel["lon"] - spill_lon) * 111.0 * math.cos(math.radians(spill_lat))
    distance = math.sqrt(dlat * dlat + dlon * dlon)

    # Convert distance into a simple 0-100 proximity score.
    score = max(0.0, 100.0 * math.exp(-distance / 35.0))

    return {
        "mmsi": vessel["mmsi"],
        "name": vessel["name"],
        "distance_km": round(distance, 2),
        "baseline_score": round(score, 1),
        "selection_reason": "Closest vessel to observed slick",
    }


def generate_baseline_analysis(lat, lon, observation_time):
    """Generate the deliberately naive baseline attribution result."""
    candidates = [
        baseline_distance_score(v, lat, lon)
        for v in VESSELS
    ]
    candidates.sort(key=lambda x: x["distance_km"])

    return {
        "method": "BASELINE",
        "method_description": "Rank vessels only by proximity to the observed slick.",
        "incident": {
            "observed_at": observation_time.isoformat(),
            "slick": {
                "lat": lat,
                "lon": lon,
                "area_km2": 14.2,
            },
        },
        "selected_vessel": candidates[0],
        "candidates": candidates,
        "known_limitations": [
            "Does not reconstruct the spill source.",
            "Does not account for wind or ocean currents.",
            "Does not account for AIS gaps.",
            "Does not test AIS trajectory plausibility.",
            "Does not distinguish SAR look-alikes.",
        ],
    }
