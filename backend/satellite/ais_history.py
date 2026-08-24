import math
import pandas as pd


REQUIRED_COLUMNS = {
    "mmsi",
    "timestamp",
    "lat",
    "lon",
    "speed_knots",
    "heading",
}


def load_ais_history(path):
    """
    Load timestamped AIS observations.

    Used for historical trajectory analysis.
    """

    df = pd.read_csv(path)

    missing = REQUIRED_COLUMNS - set(df.columns)

    if missing:
        raise ValueError(
            "AIS history missing columns: "
            + ", ".join(sorted(missing))
        )

    df = df.copy()

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        utc=True,
        errors="coerce",
    )

    numeric_columns = [
        "lat",
        "lon",
        "speed_knots",
        "heading",
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df = df.dropna(
        subset=[
            "timestamp",
            "lat",
            "lon",
        ]
    )

    df["mmsi"] = df["mmsi"].astype(str)

    return df.sort_values(
        ["mmsi", "timestamp"]
    )


def haversine_distance(
    lat1,
    lon1,
    lat2,
    lon2,
):
    """
    Calculate great-circle distance.

    Returns kilometres.
    """

    earth_radius_km = 6371.0

    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)

    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    a = max(
        0.0,
        min(
            1.0,
            a,
        ),
    )

    return (
        2
        * earth_radius_km
        * math.atan2(
            math.sqrt(a),
            math.sqrt(1 - a),
        )
    )


def point_to_segment_distance(
    point_lat,
    point_lon,
    start_lat,
    start_lon,
    end_lat,
    end_lon,
):
    """
    Approximate minimum distance in kilometres between
    a geographic point and the AIS movement segment.

    For this short-range investigation use case,
    an equirectangular projection is sufficient.
    """

    mean_lat = math.radians(
        (
            point_lat
            + start_lat
            + end_lat
        ) / 3.0
    )

    scale_x = (
        111.0
        * math.cos(mean_lat)
    )

    scale_y = 111.0

    px = (
        point_lon
        * scale_x
    )

    py = (
        point_lat
        * scale_y
    )

    ax = (
        start_lon
        * scale_x
    )

    ay = (
        start_lat
        * scale_y
    )

    bx = (
        end_lon
        * scale_x
    )

    by = (
        end_lat
        * scale_y
    )

    dx = bx - ax
    dy = by - ay

    segment_length_squared = (
        dx * dx
        + dy * dy
    )

    if segment_length_squared == 0:

        return math.sqrt(
            (px - ax) ** 2
            + (py - ay) ** 2
        )

    t = (
        (px - ax) * dx
        + (py - ay) * dy
    ) / segment_length_squared

    t = max(
        0.0,
        min(
            1.0,
            t,
        )
    )

    closest_x = (
        ax
        + t * dx
    )

    closest_y = (
        ay
        + t * dy
    )

    return math.sqrt(
        (px - closest_x) ** 2
        + (py - closest_y) ** 2
    )


def analyze_vessel_timeline(
    history,
    mmsi,
    source_latitude,
    source_longitude,
    observation_time,
):
    """
    Analyze timestamped AIS history for one vessel.

    Detects:

        - last known AIS position
        - next known AIS position
        - AIS gap duration
        - distance from source to AIS observations
        - distance from source to the historical
          movement segment
        - whether the historical movement corridor
          is compatible with the detected source

    Historical trajectory compatibility requires:

        1. A genuine AIS gap exists.
        2. Both AIS observations surrounding the
           observation time exist.
        3. The source is close to the movement segment.

    This is investigation evidence, not proof of
    vessel responsibility.
    """

    observation_time = pd.Timestamp(
        observation_time
    )

    if observation_time.tzinfo is None:
        observation_time = (
            observation_time.tz_localize(
                "UTC"
            )
        )
    else:
        observation_time = (
            observation_time.tz_convert(
                "UTC"
            )
        )

    vessel_history = history[
        history["mmsi"] == str(mmsi)
    ].copy()

    if vessel_history.empty:

        return {
            "history_available": False,
            "ais_gap_hours": None,
            "trajectory_compatible": False,
            "trajectory_distance_km": None,
        }

    vessel_history = vessel_history.sort_values(
        "timestamp"
    )

    # ==================================================
    # 1. OBSERVATIONS BEFORE / AFTER TARGET TIME
    # ==================================================

    before = vessel_history[
        vessel_history["timestamp"]
        <= observation_time
    ]

    after = vessel_history[
        vessel_history["timestamp"]
        > observation_time
    ]

    if before.empty:
        before_point = None
    else:
        before_point = before.iloc[-1]

    if after.empty:
        after_point = None
    else:
        after_point = after.iloc[0]

    # ==================================================
    # 2. NO PREVIOUS AIS OBSERVATION
    # ==================================================

    if before_point is None:

        return {
            "history_available": True,
            "ais_gap_hours": None,
            "trajectory_compatible": False,
            "trajectory_distance_km": None,
            "last_known_position": None,
            "next_known_position": None,
        }

    last_position = {
        "latitude": float(
            before_point["lat"]
        ),
        "longitude": float(
            before_point["lon"]
        ),
        "timestamp": before_point[
            "timestamp"
        ].isoformat(),
    }

    next_position = None

    if after_point is not None:

        next_position = {
            "latitude": float(
                after_point["lat"]
            ),
            "longitude": float(
                after_point["lon"]
            ),
            "timestamp": after_point[
                "timestamp"
            ].isoformat(),
        }

    # ==================================================
    # 3. AIS GAP
    # ==================================================

    if after_point is not None:

        gap_hours = (
            after_point["timestamp"]
            - before_point["timestamp"]
        ).total_seconds() / 3600.0

    else:

        gap_hours = 0.0

    # ==================================================
    # 4. SOURCE DISTANCE FROM ENDPOINTS
    # ==================================================

    distance_from_last = haversine_distance(
        float(before_point["lat"]),
        float(before_point["lon"]),
        source_latitude,
        source_longitude,
    )

    if after_point is not None:

        distance_from_next = haversine_distance(
            float(after_point["lat"]),
            float(after_point["lon"]),
            source_latitude,
            source_longitude,
        )

    else:

        distance_from_next = None

    # ==================================================
    # 5. HISTORICAL MOVEMENT CORRIDOR
    # ==================================================

    trajectory_distance = None

    if after_point is not None:

        trajectory_distance = (
            point_to_segment_distance(
                point_lat=source_latitude,
                point_lon=source_longitude,
                start_lat=float(
                    before_point["lat"]
                ),
                start_lon=float(
                    before_point["lon"]
                ),
                end_lat=float(
                    after_point["lat"]
                ),
                end_lon=float(
                    after_point["lon"]
                ),
            )
        )

    # ==================================================
    # 6. HISTORICAL TRAJECTORY COMPATIBILITY
    #
    # We require:
    #
    #   - an actual AIS gap
    #   - observations on both sides of the target time
    #   - source close to the movement segment
    #
    # 20 km is deliberately conservative.
    # ==================================================

    trajectory_compatible = (
        after_point is not None
        and gap_hours > 0
        and trajectory_distance is not None
        and trajectory_distance <= 20.0
    )

    # ==================================================
    # 7. RETURN
    # ==================================================

    return {
        "history_available": True,

        "last_known_position": last_position,

        "next_known_position": next_position,

        "ais_gap_hours": round(
            gap_hours,
            2,
        ),

        "distance_from_last_km": round(
            distance_from_last,
            2,
        ),

        "distance_from_next_km": (
            round(
                distance_from_next,
                2,
            )
            if distance_from_next is not None
            else None
        ),

        "trajectory_distance_km": (
            round(
                trajectory_distance,
                2,
            )
            if trajectory_distance is not None
            else None
        ),

        "trajectory_compatible": (
            trajectory_compatible
        ),
    }