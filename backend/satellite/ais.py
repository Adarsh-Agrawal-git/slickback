import math
import pandas as pd


def load_vessels(path):
    """
    Load vessel positions from the AIS dataset.

    The dataset must contain:
        mmsi
        name
        lat
        lon
        speed_knots
        heading
        ais_reliability
        ais_gap_hours
        sar_support
    """

    vessels = pd.read_csv(path)

    required_columns = {
        "mmsi",
        "name",
        "lat",
        "lon",
        "speed_knots",
        "heading",
        "ais_reliability",
        "ais_gap_hours",
        "sar_support",
    }

    missing_columns = required_columns - set(vessels.columns)

    if missing_columns:
        raise ValueError(
            "AIS dataset is missing columns: "
            + ", ".join(sorted(missing_columns))
        )

    vessels = vessels.copy()

    numeric_columns = [
        "lat",
        "lon",
        "speed_knots",
        "heading",
        "ais_reliability",
        "ais_gap_hours",
        "sar_support",
    ]

    for column in numeric_columns:
        vessels[column] = pd.to_numeric(
            vessels[column],
            errors="coerce"
        )

    vessels = vessels.dropna(
        subset=["lat", "lon"]
    )

    return vessels


def haversine_distance(
    latitude_1,
    longitude_1,
    latitude_2,
    longitude_2
):
    """
    Calculate great-circle distance between
    two geographic coordinates.

    Returns distance in kilometres.
    """

    earth_radius_km = 6371.0

    lat1 = math.radians(latitude_1)
    lon1 = math.radians(longitude_1)

    lat2 = math.radians(latitude_2)
    lon2 = math.radians(longitude_2)

    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(delta_lon / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )

    return earth_radius_km * c


def find_nearby_vessels(
    vessels,
    latitude,
    longitude,
    radius_km
):
    """
    Find AIS vessels within the requested
    geographic radius of a candidate.
    """

    if radius_km <= 0:
        raise ValueError(
            "radius_km must be greater than zero."
        )

    results = []

    for _, vessel in vessels.iterrows():

        distance_km = haversine_distance(
            latitude,
            longitude,
            vessel["lat"],
            vessel["lon"]
        )

        if distance_km > radius_km:
            continue

        results.append({
            "mmsi": str(vessel["mmsi"]),
            "name": str(vessel["name"]),
            "latitude": float(vessel["lat"]),
            "longitude": float(vessel["lon"]),
            "speed_knots": float(vessel["speed_knots"]),
            "heading": float(vessel["heading"]),
            "ais_reliability": float(
                vessel["ais_reliability"]
            ),
            "ais_gap_hours": float(
                vessel["ais_gap_hours"]
            ),
            "sar_support": float(
                vessel["sar_support"]
            ),
            "distance_km": round(
                distance_km,
                3
            ),
        })

    return results


def rank_vessels(
    vessels,
    latitude,
    longitude,
    radius_km
):
    """
    Find and rank vessels near a detected
    Sentinel-1 candidate.

    Ranking uses only measurements contained
    in the supplied AIS dataset.

    No vessel identity or position is hardcoded.
    """

    nearby_vessels = find_nearby_vessels(
        vessels,
        latitude,
        longitude,
        radius_km
    )

    if not nearby_vessels:
        return []

    distances = [
        vessel["distance_km"]
        for vessel in nearby_vessels
    ]

    max_distance = max(distances)

    for vessel in nearby_vessels:

        if max_distance > 0:
            distance_score = (
                1
                - vessel["distance_km"]
                / max_distance
            )
        else:
            distance_score = 1.0

        reliability_score = max(
            0.0,
            min(
                1.0,
                vessel["ais_reliability"]
            )
        )

        gap_score = 1.0 / (
            1.0
            + max(
                0.0,
                vessel["ais_gap_hours"]
            )
        )

        sar_support_score = max(
            0.0,
            min(
                1.0,
                vessel["sar_support"]
            )
        )

        vessel["distance_score"] = round(
            distance_score,
            3
        )

        vessel["reliability_score"] = round(
            reliability_score,
            3
        )

        vessel["gap_score"] = round(
            gap_score,
            3
        )

        vessel["sar_support_score"] = round(
            sar_support_score,
            3
        )

        vessel["correlation_score"] = round(
            (
                distance_score
                + reliability_score
                + gap_score
                + sar_support_score
            ) / 4.0,
            3
        )

    nearby_vessels.sort(
        key=lambda vessel: (
            vessel["correlation_score"],
            -vessel["distance_km"]
        ),
        reverse=True
    )

    return nearby_vessels