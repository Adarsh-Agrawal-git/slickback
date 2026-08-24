import math


def destination_from_motion(
    latitude,
    longitude,
    speed_knots,
    heading_deg,
    hours,
):
    """
    Estimate a bounded previous position from the vessel's
    current motion.

    IMPORTANT:
    This is a motion-based estimate, NOT historical AIS data.
    """

    speed_kmh = max(
        0.0,
        float(speed_knots),
    ) * 1.852

    # Do not extrapolate current heading indefinitely.
    effective_hours = min(
        max(0.0, float(hours)),
        6.0,
    )

    distance_km = (
        speed_kmh
        * effective_hours
    )

    bearing = math.radians(
        float(heading_deg)
    )

    north_km = (
        -distance_km
        * math.cos(bearing)
    )

    east_km = (
        -distance_km
        * math.sin(bearing)
    )

    historical_latitude = (
        float(latitude)
        + north_km / 111.0
    )

    lon_scale = max(
        math.cos(
            math.radians(
                float(latitude)
            )
        ),
        0.2,
    )

    historical_longitude = (
        float(longitude)
        + east_km
        / (111.0 * lon_scale)
    )

    return {
        "latitude": historical_latitude,
        "longitude": historical_longitude,
        "effective_hours": effective_hours,
    }


def haversine_distance(
    latitude_1,
    longitude_1,
    latitude_2,
    longitude_2,
):
    """
    Calculate great-circle distance.

    Returns kilometres.
    """

    earth_radius_km = 6371.0

    lat1 = math.radians(
        latitude_1
    )
    lon1 = math.radians(
        longitude_1
    )

    lat2 = math.radians(
        latitude_2
    )
    lon2 = math.radians(
        longitude_2
    )

    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(delta_lon / 2) ** 2
    )

    a = max(
        0.0,
        min(1.0, a),
    )

    return (
        2
        * earth_radius_km
        * math.atan2(
            math.sqrt(a),
            math.sqrt(1.0 - a),
        )
    )


def evaluate_vessel_evidence(
    vessel,
    source_latitude,
    source_longitude,
    hours_back,
):
    """
    Evaluate evidence connecting a vessel to a
    reconstructed spill source.

    This is an investigation-support score.

    It does NOT prove legal responsibility.
    """

    current_latitude = float(
        vessel["latitude"]
    )

    current_longitude = float(
        vessel["longitude"]
    )

    speed_knots = max(
        0.0,
        float(vessel["speed_knots"]),
    )

    heading = float(
        vessel["heading"]
    )

    ais_gap_hours = max(
        0.0,
        float(vessel["ais_gap_hours"]),
    )

    reliability = max(
        0.0,
        min(
            1.0,
            float(vessel["ais_reliability"]),
        ),
    )

    # ==================================================
    # 1. MOTION-BASED SOURCE ESTIMATE
    # ==================================================

    estimated_position = destination_from_motion(
        latitude=current_latitude,
        longitude=current_longitude,
        speed_knots=speed_knots,
        heading_deg=heading,
        hours=hours_back,
    )

    estimated_latitude = (
        estimated_position["latitude"]
    )

    estimated_longitude = (
        estimated_position["longitude"]
    )

    source_distance = haversine_distance(
        estimated_latitude,
        estimated_longitude,
        source_latitude,
        source_longitude,
    )

    # ==================================================
    # 2. PHYSICAL REACHABILITY
    #
    # Can this vessel physically cover the distance
    # between its current position and the reconstructed
    # source within the investigation window?
    # ==================================================

    maximum_travel_distance = (
        speed_knots
        * 1.852
        * max(
            float(hours_back),
            1.0,
        )
    )

    physically_reachable = (
        source_distance
        <= maximum_travel_distance
    )

    # ==================================================
    # 3. SOURCE COMPATIBILITY
    #
    # This is the strongest evidence.
    # A vessel far outside its physically possible
    # source region should not receive strong evidence
    # merely because it has an AIS gap.
    # ==================================================

    if not physically_reachable:

        source_match = 0.0

    else:

        source_match = max(
            0.0,
            100.0 * math.exp(
                -source_distance / 15.0
            ),
        )

    # ==================================================
    # 4. AIS GAP
    # ==================================================

    if ais_gap_hours <= 0:

        gap_score = 0.0

    else:

        gap_score = min(
            100.0,
            25.0
            + 50.0
            * min(
                ais_gap_hours,
                max(
                    float(hours_back),
                    1.0,
                ),
            )
            / max(
                float(hours_back),
                1.0,
            ),
        )

    # ==================================================
    # 5. KINEMATIC ANOMALY
    # ==================================================

    if speed_knots <= 20:

        kinematic_score = 0.0

    elif speed_knots <= 25:

        kinematic_score = 20.0

    else:

        kinematic_score = min(
            100.0,
            20.0
            + (
                speed_knots - 25.0
            ) * 4.0,
        )

    kinematic_anomaly = (
        speed_knots > 25
    )

    # ==================================================
    # 6. AIS RELIABILITY
    # ==================================================

    reliability_score = (
        reliability * 100.0
    )

    # ==================================================
    # 7. EVIDENCE FUSION
    #
    # Source compatibility dominates.
    # AIS gaps and kinematics support the investigation.
    # ==================================================

    evidence_score = (
        0.55 * source_match
        + 0.20 * reliability_score
        + 0.15 * gap_score
        + 0.10 * kinematic_score
    )

    # ==================================================
    # 8. FLAGS
    # ==================================================

    flags = []

    if physically_reachable:
        flags.append(
            "PHYSICALLY REACHABLE"
        )

    if source_match >= 60:
        flags.append(
            "SOURCE TRAJECTORY COMPATIBLE"
        )

    if ais_gap_hours > 0:
        flags.append(
            "AIS GAP"
        )

    if kinematic_anomaly:
        flags.append(
            "KINEMATIC ANOMALY"
        )

    if reliability < 0.7:
        flags.append(
            "LOW AIS RELIABILITY"
        )

    # ==================================================
    # 9. INTENTIONAL-DISCHARGE INDICATORS
    #
    # We only count suspicious behaviour when the vessel
    # is also compatible with the spill source.
    # ==================================================

    intentional_indicators = 0

    if source_match >= 60:
        intentional_indicators += 1

    if (
        source_match >= 60
        and ais_gap_hours > 0
    ):
        intentional_indicators += 1

    if (
        source_match >= 60
        and kinematic_anomaly
    ):
        intentional_indicators += 1

    # ==================================================
    # 10. INVESTIGATION ASSESSMENT
    # ==================================================

    if (
        source_match >= 60
        and intentional_indicators >= 2
    ):

        assessment = (
            "POTENTIALLY INTENTIONAL"
        )

    elif source_match >= 60:

        assessment = (
            "POTENTIALLY ACCIDENTAL"
        )

    elif (
        ais_gap_hours > 0
        or kinematic_anomaly
    ):

        assessment = (
            "ANOMALY REQUIRES INVESTIGATION"
        )

    else:

        assessment = (
            "INSUFFICIENT EVIDENCE"
        )

    # ==================================================
    # 11. RETURN INVESTIGATION RESULT
    # ==================================================

    return {

        "estimated_historical_position": {
            "latitude": round(
                estimated_latitude,
                6,
            ),
            "longitude": round(
                estimated_longitude,
                6,
            ),
        },

        "motion_estimate_hours": round(
            estimated_position[
                "effective_hours"
            ],
            2,
        ),

        "source_distance_km": round(
            source_distance,
            2,
        ),

        "maximum_travel_distance_km": round(
            maximum_travel_distance,
            2,
        ),

        "physically_reachable": (
            physically_reachable
        ),

        "source_trajectory_match": round(
            source_match,
            1,
        ),

        "ais_gap_hours": round(
            ais_gap_hours,
            2,
        ),

        "ais_gap_indicator": (
            ais_gap_hours > 0
        ),

        "kinematic_anomaly": (
            kinematic_anomaly
        ),

        "kinematic_score": round(
            kinematic_score,
            1,
        ),

        "ais_reliability": round(
            reliability,
            3,
        ),

        "evidence_score": round(
            evidence_score,
            1,
        ),

        "flags": flags,

        "intentional_indicators": (
            intentional_indicators
        ),

        "assessment": assessment,
    }