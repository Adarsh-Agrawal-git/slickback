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
    source_time=None,
):
    """
    Analyze timestamped AIS history for one vessel around the
    reconstructed spill-source time.

    This function deliberately does NOT extrapolate a vessel beyond
    its observed AIS history. If the requested source time is outside
    the available history, the result is marked as out-of-coverage.

    Evidence includes:
        - AIS history coverage
        - observations immediately before/after target time
        - AIS gap duration
        - source distance from observed positions
        - distance from source to the historical movement segment
        - trajectory compatibility
        - interpolated position when observations bracket target time

    `source_time` should normally be the reconstructed release/source
    time. If omitted, observation_time is used for backwards
    compatibility.

    This is investigation evidence, not proof of responsibility.
    """

    def normalize_timestamp(value):
        ts = pd.Timestamp(value)

        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        else:
            ts = ts.tz_convert("UTC")

        return ts

    observation_time = normalize_timestamp(
        observation_time
    )

    if source_time is None:
        target_time = observation_time
    else:
        target_time = normalize_timestamp(
            source_time
        )

    vessel_history = history[
        history["mmsi"] == str(mmsi)
    ].copy()

    if vessel_history.empty:
        return {
            "history_available": False,
            "history_coverage": False,
            "target_time": target_time.isoformat(),
            "ais_gap_hours": None,
            "trajectory_compatible": False,
            "trajectory_distance_km": None,
            "reason": "No AIS history found for this MMSI.",
        }

    vessel_history = vessel_history.sort_values(
        "timestamp"
    ).dropna(
        subset=[
            "timestamp",
            "lat",
            "lon",
        ]
    )

    if vessel_history.empty:
        return {
            "history_available": False,
            "history_coverage": False,
            "target_time": target_time.isoformat(),
            "ais_gap_hours": None,
            "trajectory_compatible": False,
            "trajectory_distance_km": None,
            "reason": "AIS history contains no valid timestamped positions.",
        }

    history_start = vessel_history["timestamp"].iloc[0]
    history_end = vessel_history["timestamp"].iloc[-1]

    coverage_before = target_time >= history_start
    coverage_after = target_time <= history_end

    before = vessel_history[
        vessel_history["timestamp"] <= target_time
    ]

    after = vessel_history[
        vessel_history["timestamp"] > target_time
    ]

    before_point = (
        before.iloc[-1]
        if not before.empty
        else None
    )

    after_point = (
        after.iloc[0]
        if not after.empty
        else None
    )

    history_coverage = (
        before_point is not None
        and after_point is not None
    )

    if before_point is None:
        return {
            "history_available": True,
            "history_coverage": False,
            "target_time": target_time.isoformat(),
            "history_start": history_start.isoformat(),
            "history_end": history_end.isoformat(),
            "ais_gap_hours": None,
            "trajectory_compatible": False,
            "trajectory_distance_km": None,
            "last_known_position": None,
            "next_known_position": (
                {
                    "latitude": float(after_point["lat"]),
                    "longitude": float(after_point["lon"]),
                    "timestamp": after_point["timestamp"].isoformat(),
                }
                if after_point is not None
                else None
            ),
            "reason": "Target time is before available AIS history.",
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

    # ---------------------------------------------------------
    # AIS gap surrounding the target/source time
    # ---------------------------------------------------------

    if after_point is not None:
        gap_hours = (
            after_point["timestamp"]
            - before_point["timestamp"]
        ).total_seconds() / 3600.0
    else:
        # There is no post-target observation, so this is not a
        # bracketing gap. Keep it explicit instead of pretending
        # the last observation proves what happened afterward.
        gap_hours = None

    # ---------------------------------------------------------
    # Distances from source to observed AIS positions
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # Historical movement corridor
    # ---------------------------------------------------------

    trajectory_distance = None

    if after_point is not None:
        trajectory_distance = point_to_segment_distance(
            point_lat=source_latitude,
            point_lon=source_longitude,
            start_lat=float(before_point["lat"]),
            start_lon=float(before_point["lon"]),
            end_lat=float(after_point["lat"]),
            end_lon=float(after_point["lon"]),
        )

    # ---------------------------------------------------------
    # Interpolated position at target time
    # ---------------------------------------------------------

    interpolated_position = None

    if after_point is not None:
        total_seconds = (
            after_point["timestamp"]
            - before_point["timestamp"]
        ).total_seconds()

        if total_seconds > 0:
            elapsed_seconds = (
                target_time
                - before_point["timestamp"]
            ).total_seconds()

            fraction = (
                elapsed_seconds
                / total_seconds
            )

            fraction = max(
                0.0,
                min(
                    1.0,
                    fraction,
                ),
            )

            interpolated_lat = (
                float(before_point["lat"])
                + fraction
                * (
                    float(after_point["lat"])
                    - float(before_point["lat"])
                )
            )

            interpolated_lon = (
                float(before_point["lon"])
                + fraction
                * (
                    float(after_point["lon"])
                    - float(before_point["lon"])
                )
            )

            interpolated_distance = haversine_distance(
                interpolated_lat,
                interpolated_lon,
                source_latitude,
                source_longitude,
            )

            interpolated_position = {
                "latitude": round(
                    interpolated_lat,
                    6,
                ),
                "longitude": round(
                    interpolated_lon,
                    6,
                ),
                "distance_to_source_km": round(
                    interpolated_distance,
                    2,
                ),
                "method": "linear_interpolation_between_AIS_observations",
            }

    # ---------------------------------------------------------
    # Track movement speed between bracketing observations
    # ---------------------------------------------------------

    segment_speed_knots = None

    if after_point is not None:
        segment_distance = haversine_distance(
            float(before_point["lat"]),
            float(before_point["lon"]),
            float(after_point["lat"]),
            float(after_point["lon"]),
        )

        if gap_hours is not None and gap_hours > 0:
            segment_speed_kmh = (
                segment_distance / gap_hours
            )

            segment_speed_knots = (
                segment_speed_kmh / 1.852
            )

    # ---------------------------------------------------------
    # Historical trajectory compatibility
    #
    # A vessel is considered trajectory-compatible only when:
    #   1. target time is actually bracketed by AIS observations
    #   2. there is a genuine time interval
    #   3. the source is close to that observed movement corridor
    #
    # No extrapolation is performed.
    # ---------------------------------------------------------

    trajectory_compatible = (
        history_coverage
        and gap_hours is not None
        and gap_hours > 0
        and trajectory_distance is not None
        and trajectory_distance <= 20.0
    )

    if trajectory_compatible:
        compatibility_reason = (
            "AIS observations bracket the target source time "
            "and the source lies within 20 km of the observed "
            "historical movement corridor."
        )
    elif not history_coverage:
        compatibility_reason = (
            "Target source time is not bracketed by AIS observations; "
            "no trajectory compatibility claim is made."
        )
    else:
        compatibility_reason = (
            "AIS observations bracket the target time, but the "
            "historical movement corridor is more than 20 km from "
            "the reconstructed source."
        )

    return {
        "history_available": True,
        "history_coverage": bool(history_coverage),
        "target_time": target_time.isoformat(),
        "history_start": history_start.isoformat(),
        "history_end": history_end.isoformat(),
        "target_within_history": bool(
            coverage_before and coverage_after
        ),
        "last_known_position": last_position,
        "next_known_position": next_position,
        "interpolated_position": interpolated_position,
        "ais_gap_hours": (
            round(
                gap_hours,
                2,
            )
            if gap_hours is not None
            else None
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
        "segment_speed_knots": (
            round(
                segment_speed_knots,
                2,
            )
            if segment_speed_knots is not None
            else None
        ),
        "trajectory_compatible": bool(
            trajectory_compatible
        ),
        "compatibility_reason": compatibility_reason,
        "extrapolation_used": False,
    }
