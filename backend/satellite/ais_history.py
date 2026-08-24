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

    This module is used for trajectory analysis.
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

    return (
        2
        * earth_radius_km
        * math.atan2(
            math.sqrt(a),
            math.sqrt(1 - a),
        )
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
        - last known position
        - next known position
        - AIS gaps
        - distance from source
        - whether the source falls inside the
          temporal movement corridor
    """

    observation_time = pd.Timestamp(
        observation_time,
        tz="UTC",
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

    # ------------------------------------------
    # No surrounding observations
    # ------------------------------------------

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
        "latitude": float(before_point["lat"]),
        "longitude": float(before_point["lon"]),
        "timestamp": before_point[
            "timestamp"
        ].isoformat(),
    }

    next_position = None

    if after_point is not None:
        next_position = {
            "latitude": float(after_point["lat"]),
            "longitude": float(after_point["lon"]),
            "timestamp": after_point[
                "timestamp"
            ].isoformat(),
        }

    # ------------------------------------------
    # AIS gap
    # ------------------------------------------

    if after_point is not None:

        gap_hours = (
            after_point["timestamp"]
            - before_point["timestamp"]
        ).total_seconds() / 3600.0

    else:

        gap_hours = 0.0

    # ------------------------------------------
    # Distance from source to last observation
    # ------------------------------------------

    distance_from_last = haversine_distance(
        float(before_point["lat"]),
        float(before_point["lon"]),
        source_latitude,
        source_longitude,
    )

    # ------------------------------------------
    # Distance from source to next observation
    # ------------------------------------------

    if after_point is not None:

        distance_from_next = haversine_distance(
            float(after_point["lat"]),
            float(after_point["lon"]),
            source_latitude,
            source_longitude,
        )

    else:

        distance_from_next = None

    # ------------------------------------------
    # Trajectory compatibility
    #
    # If the source is reasonably close to either
    # side of an AIS gap, flag it for investigation.
    # ------------------------------------------

    trajectory_compatible = (
        gap_hours > 0
        and (
            distance_from_last <= 50
            or (
                distance_from_next is not None
                and distance_from_next <= 50
            )
        )
    )

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

        "trajectory_compatible": (
            trajectory_compatible
        ),
    }