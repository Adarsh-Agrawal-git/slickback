from satellite.ais_history import (
    load_ais_history,
    analyze_vessel_timeline,
)

from investigation import (
    evaluate_vessel_evidence,
)

from satellite.sentinel1 import (
    download_sentinel1_scientific,
    pixel_to_latlon,
)

from satellite.preprocess import (
    load_sentinel1,
    to_db,
    remove_speckle,
)

from satellite.detect import (
    detect_dark_regions,
    extract_candidates,
)

from satellite.candidate_scoring import (
    extract_candidate_features,
)

from satellite.ais import (
    load_vessels,
    rank_vessels,
)


def run_pipeline(
    latitude,
    longitude,
    start_datetime,
    end_datetime,
    hours_back,
    vessel_data_path,
    ais_history_path,
    observation_time,
    image_output_path,
    radius_km,
    bbox_delta,
    image_size,
    min_candidate_area,
):
    """
    Real Sentinel-1 -> SAR candidate -> AIS ->
    historical AIS investigation pipeline.

    Pipeline:

        1. Download real Sentinel-1 GRD data.
        2. Load VV backscatter.
        3. Convert VV to dB.
        4. Reduce speckle.
        5. Detect dark SAR regions.
        6. Extract candidate regions.
        7. Convert candidate pixels to coordinates.
        8. Extract SAR features.
        9. Load current AIS vessel data.
        10. Load timestamped AIS history.
        11. Find nearby vessels.
        12. Evaluate vessel/source compatibility.
        13. Analyze historical AIS trajectory and gaps.
        14. Combine evidence.
        15. Rank vessels for investigation.

    Investigation results are leads,
    not legal proof of responsibility.
    """

    # ==================================================
    # 1. DOWNLOAD REAL SENTINEL-1 DATA
    # ==================================================

    acquisition = download_sentinel1_scientific(
        latitude=latitude,
        longitude=longitude,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        output_path=image_output_path,
        size=image_size,
        delta=bbox_delta,
    )

    image_path = acquisition["path"]
    bbox = acquisition["bbox"]

    # ==================================================
    # 2. LOAD SENTINEL-1
    # ==================================================

    vv = load_sentinel1(
        image_path
    )

    # ==================================================
    # 3. PREPROCESS
    # ==================================================

    vv_db = to_db(
        vv
    )

    vv_filtered = remove_speckle(
        vv_db
    )

    # ==================================================
    # 4. DETECT DARK SAR REGIONS
    # ==================================================

    (
        candidate_mask,
        contrast,
        threshold,
    ) = detect_dark_regions(
        vv_filtered
    )

    candidates = extract_candidates(
        candidate_mask,
        min_area=min_candidate_area,
    )

    # ==================================================
    # 5. PIXEL -> GEOGRAPHIC COORDINATES
    # ==================================================

    image_height, image_width = vv.shape

    geographic_candidates = []

    for candidate in candidates:

        location = pixel_to_latlon(
            row=candidate["centroid_row"],
            col=candidate["centroid_col"],
            image_height=image_height,
            image_width=image_width,
            bbox=bbox,
        )

        geographic_candidates.append({
            **candidate,
            **location,
        })

    # ==================================================
    # 6. EXTRACT SAR FEATURES
    # ==================================================

    candidate_features = (
        extract_candidate_features(
            vv_db=vv_filtered,
            candidate_mask=candidate_mask,
            candidates=geographic_candidates,
        )
    )

    # ==================================================
    # 7. LOAD CURRENT AIS DATA
    # ==================================================

    vessels = load_vessels(
        vessel_data_path
    )

    # ==================================================
    # 8. LOAD HISTORICAL AIS DATA
    # ==================================================

    ais_history = load_ais_history(
        ais_history_path
    )

    results = []

    # ==================================================
    # 9. AIS + INVESTIGATION
    # ==================================================

    for candidate in candidate_features:

        nearby_vessels = rank_vessels(
            vessels=vessels,
            latitude=candidate["latitude"],
            longitude=candidate["longitude"],
            radius_km=radius_km,
        )

        investigated_vessels = []

        # ==================================================
        # Analyze every nearby vessel
        # ==================================================

        for vessel in nearby_vessels:

            # ------------------------------------------
            # Motion/source investigation
            # ------------------------------------------

            investigation = (
                evaluate_vessel_evidence(
                    vessel=vessel,
                    source_latitude=candidate["latitude"],
                    source_longitude=candidate["longitude"],
                    hours_back=hours_back,
                )
            )

            # ------------------------------------------
            # Historical AIS trajectory investigation
            # ------------------------------------------

            timeline = analyze_vessel_timeline(
                history=ais_history,
                mmsi=vessel["mmsi"],
                source_latitude=candidate["latitude"],
                source_longitude=candidate["longitude"],
                observation_time=observation_time,
            )

            # ------------------------------------------
            # Combine vessel information
            # ------------------------------------------

            vessel_result = {
                **vessel,
                "investigation": investigation,
                "timeline": timeline,
            }

            # ------------------------------------------
            # Historical AIS indicators
            # ------------------------------------------

            timeline_gap = timeline.get(
                "ais_gap_hours"
            )

            ais_trajectory_compatible = timeline.get(
                "trajectory_compatible",
                False,
            )

            # ------------------------------------------
            # Combined responsibility score
            #
            # This is an investigation priority score.
            # It is NOT proof of responsibility.
            # ------------------------------------------

            correlation_component = (
                0.40
                * vessel["correlation_score"]
                * 100.0
            )

            investigation_component = (
                0.50
                * investigation["evidence_score"]
            )

            timeline_component = 0.0

            # Historical AIS trajectory compatibility
            if ais_trajectory_compatible:
                timeline_component += 10.0

            # Historical AIS gap
            if (
                timeline_gap is not None
                and timeline_gap > 0
            ):
                timeline_component += min(
                    10.0,
                    timeline_gap * 2.0,
                )

            responsibility_score = (
                correlation_component
                + investigation_component
                + timeline_component
            )

            vessel_result[
                "responsibility_score"
            ] = round(
                responsibility_score,
                1,
            )

            # ------------------------------------------
            # Investigation flags
            # ------------------------------------------

            flags = list(
                investigation.get(
                    "flags",
                    []
                )
            )

            # Historical AIS gap
            if (
                timeline_gap is not None
                and timeline_gap > 0
            ):
                if (
                    "AIS TIMELINE GAP"
                    not in flags
                ):
                    flags.append(
                        "AIS TIMELINE GAP"
                    )

            # Historical AIS trajectory
            if ais_trajectory_compatible:

                if (
                    "AIS TRAJECTORY COMPATIBLE"
                    not in flags
                ):
                    flags.append(
                        "AIS TRAJECTORY COMPATIBLE"
                    )

            # ------------------------------------------
            # Priority classification
            # ------------------------------------------

            if (
                ais_trajectory_compatible
                and timeline_gap is not None
                and timeline_gap >= 2
            ):

                priority = (
                    "HIGH PRIORITY INVESTIGATION"
                )

            elif (
                investigation["kinematic_anomaly"]
                and investigation[
                    "ais_reliability"
                ] < 0.7
            ):

                priority = (
                    "HIGH PRIORITY INVESTIGATION"
                )

            elif (
                timeline_gap is not None
                and timeline_gap > 0
            ):

                priority = (
                    "ANOMALY REQUIRES INVESTIGATION"
                )

            elif investigation[
                "kinematic_anomaly"
            ]:

                priority = (
                    "ANOMALY REQUIRES INVESTIGATION"
                )

            elif investigation[
                "source_distance_km"
            ] <= 20:

                priority = (
                    "POTENTIALLY COMPATIBLE"
                )

            else:

                priority = (
                    "INSUFFICIENT EVIDENCE"
                )

            # ------------------------------------------
            # Final investigation object
            # ------------------------------------------

            vessel_result[
                "investigation"
            ] = {
                **investigation,

                "flags": flags,

                "priority": priority,
            }

            investigated_vessels.append(
                vessel_result
            )

        # ==================================================
        # 10. RANK VESSELS
        # ==================================================

        investigated_vessels.sort(
            key=lambda vessel: (
                vessel[
                    "responsibility_score"
                ],
                vessel[
                    "investigation"
                ][
                    "evidence_score"
                ],
            ),
            reverse=True,
        )

        results.append({
            "candidate": candidate,

            "nearby_vessels": (
                investigated_vessels
            ),
        })

    # ==================================================
    # 11. RETURN COMPLETE RESULT
    # ==================================================

    return {
        "status": "success",

        "satellite": {
            "source": (
                "Copernicus Data Space"
            ),

            "mission": (
                "Sentinel-1"
            ),

            "product": (
                "sentinel-1-grd"
            ),

            "bbox": bbox,

            "image_size": [
                int(image_height),
                int(image_width),
            ],

            "adaptive_threshold_db": round(
                float(threshold),
                3,
            ),
        },

        "detection": {
            "candidate_count": len(
                candidate_features
            ),
        },

        "investigation": {
            "hours_back": hours_back,

            "method": (
                "SAR candidate detection + "
                "AIS spatial correlation + "
                "historical AIS timeline analysis + "
                "motion-based source compatibility + "
                "anomaly analysis"
            ),

            "ais_history": {
                "enabled": True,

                "source": (
                    "Timestamped AIS history "
                    "provided to the pipeline"
                ),
            },

            "disclaimer": (
                "Investigation indicators are "
                "not legal proof of responsibility."
            ),
        },

        "candidates": results,
    }