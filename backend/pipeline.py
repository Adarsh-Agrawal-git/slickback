import numpy as np
from datetime import datetime, timedelta
from satellite.sentinel2 import validate_sentinel2_candidate
from environment import fetch_environment
from simulation import backward_particles

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


# ============================================================
# MAIN PIPELINE
# ============================================================

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
    SlickBack investigation pipeline.

    Flow:

        Real Sentinel-1
              ↓
        VV backscatter
              ↓
        dB conversion
              ↓
        Speckle reduction
              ↓
        Dark-region detection
              ↓
        Candidate extraction
              ↓
        Pixel → latitude/longitude
              ↓
        SAR feature extraction
              ↓
        AIS correlation
              ↓
        Historical AIS analysis
              ↓
        Environmental wind/current
              ↓
        Backward particle hindcast
              ↓
        Vessel investigation
              ↓
        Investigation priority

    IMPORTANT:
    The resulting vessel ranking is an investigation lead,
    NOT legal proof that a vessel caused an oil spill.
    """

    # ========================================================
    # NORMALIZE OBSERVATION TIME
    # ========================================================

    if isinstance(observation_time, str):
        observation_time = datetime.fromisoformat(
            observation_time.replace(
                "Z",
                "+00:00",
            )
        )

    # ========================================================
    # 1. DOWNLOAD REAL SENTINEL-1 DATA
    # ========================================================

    print("\n")
    print("=" * 60)
    print("SLICKBACK PIPELINE")
    print("=" * 60)

    print("Location:")
    print("  Latitude :", latitude)
    print("  Longitude:", longitude)

    print("Time:")
    print("  From     :", start_datetime)
    print("  To       :", end_datetime)

    print("=" * 60)

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

    # ========================================================
    # 2. REAL SENTINEL-1 METADATA
    # ========================================================

    satellite_metadata = {
        "scene_id": acquisition.get(
            "scene_id"
        ),
        "acquisition_time": acquisition.get(
            "acquisition_time"
        ),
        "orbit_pass": acquisition.get(
            "orbit_pass"
        ),
        "relative_orbit": acquisition.get(
            "relative_orbit"
        ),
        "instrument_mode": acquisition.get(
            "instrument_mode"
        ),
        "polarization": acquisition.get(
            "polarization"
        ),
    }

    print("\nSentinel-1 scene selected:")

    print(
        "  Scene:",
        satellite_metadata["scene_id"],
    )

    print(
        "  Acquisition:",
        satellite_metadata["acquisition_time"],
    )

    print(
        "  Orbit:",
        satellite_metadata["orbit_pass"],
    )

    # ========================================================
    # 3. LOAD SENTINEL-1 IMAGE
    # ========================================================

    print("\nLoading Sentinel-1 image...")

    vv = load_sentinel1(
        image_path
    )

    # ========================================================
    # 4. CONVERT TO dB
    # ========================================================

    print(
        "Converting VV backscatter to dB..."
    )

    vv_db = to_db(
        vv
    )

    # ========================================================
    # 5. REDUCE SPECKLE
    # ========================================================

    print(
        "Reducing speckle..."
    )

    vv_filtered = remove_speckle(
        vv_db
    )

    # ========================================================
    # 6. DETECT DARK SAR REGIONS
    # ========================================================

    print(
        "Detecting dark SAR regions..."
    )

    (
        candidate_mask,
        contrast,
        threshold,
    ) = detect_dark_regions(
        vv_filtered
    )

    # ========================================================
    # 7. EXTRACT CANDIDATES
    # ========================================================

    print(
        "Extracting candidate regions..."
    )

    candidates = extract_candidates(
        candidate_mask,
        min_area=min_candidate_area,
    )

    print(
        "Candidate regions detected:",
        len(candidates),
    )

    # ========================================================
    # 8. PIXEL → GEOGRAPHIC COORDINATES
    # ========================================================

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

    # ========================================================
    # 9. EXTRACT SAR FEATURES
    # ========================================================

    print(
        "Extracting SAR candidate features..."
    )

    candidate_features = extract_candidate_features(
        vv_db=vv_filtered,
        candidate_mask=candidate_mask,
        candidates=geographic_candidates,
    )

    # ========================================================
    # 9A. RANK SAR CANDIDATES
    # ========================================================
    #
    # Do not run expensive environmental/AIS investigation on
    # every raw dark region. First prioritize the strongest
    # geometric SAR anomalies.
    #
    # This is a triage step, NOT an oil classifier.
    # ========================================================

    def sar_priority_score(candidate):
        area = float(candidate.get("area_pixels", 0.0))
        aspect = float(candidate.get("aspect_ratio", 1.0))
        eccentricity = float(candidate.get("eccentricity", 0.0))
        solidity = float(candidate.get("solidity", 0.0))
        extent = float(candidate.get("extent", 0.0))

        # Favor elongated structures, reasonable compactness,
        # and sufficiently large connected regions.
        area_score = min(area / 100.0, 1.0)
        elongation_score = min(max((aspect - 1.0) / 4.0, 0.0), 1.0)
        eccentricity_score = min(max(eccentricity, 0.0), 1.0)
        solidity_score = min(max(solidity, 0.0), 1.0)
        extent_score = min(max(extent, 0.0), 1.0)

        return (
            0.20 * area_score
            + 0.25 * elongation_score
            + 0.25 * eccentricity_score
            + 0.15 * solidity_score
            + 0.15 * extent_score
        ) * 100.0

    for candidate in candidate_features:
        candidate["sar_priority_score"] = round(
            sar_priority_score(candidate),
            2,
        )

    candidate_features.sort(
        key=lambda candidate: candidate["sar_priority_score"],
        reverse=True,
    )

    raw_candidate_count = len(candidate_features)

    # Investigate only the strongest candidates. This prevents
    # 50+ weak dark regions from triggering repeated environmental
    # and AIS processing.
    max_investigation_candidates = 12

    candidate_features = candidate_features[
        :max_investigation_candidates
    ]

    print()
    print("SAR CANDIDATE TRIAGE")
    print("Raw candidates:", raw_candidate_count)
    print(
        "Candidates selected for investigation:",
        len(candidate_features),
    )

    for rank, candidate in enumerate(
        candidate_features,
        start=1,
    ):
        print(
            f"  #{rank}: "
            f"{candidate.get('latitude', 0):.5f}, "
            f"{candidate.get('longitude', 0):.5f} "
            f"score={candidate['sar_priority_score']:.2f}"
        )
            # ========================================================
    # 9B. SENTINEL-2 CROSS VALIDATION
    # ========================================================

    print()
    print("=" * 60)
    print("SENTINEL-2 CROSS VALIDATION")
    print("=" * 60)

    for candidate_index, candidate in enumerate(
        candidate_features,
        start=1,
    ):

        print(
            f"\nValidating candidate {candidate_index}/"
            f"{len(candidate_features)} with Sentinel-2..."
        )

        try:

            sentinel2_validation = (
                validate_sentinel2_candidate(
                    latitude=candidate["latitude"],
                    longitude=candidate["longitude"],
                    acquisition_time=(
                        satellite_metadata["acquisition_time"]
                    ),
                    search_hours=120,
                )
            )

        except Exception as error:

            print(
                "WARNING: Sentinel-2 validation failed:",
                repr(error),
            )

            sentinel2_validation = {
                "available": False,
                "validated": False,
                "confidence": 0.0,
                "reason": str(error),
            }

        candidate["sentinel2_validation"] = (
            sentinel2_validation
        )

    # ========================================================
    # 10. LOAD AIS DATA
    # ========================================================

    print(
        "Loading AIS vessel data..."
    )

    vessels = load_vessels(
        vessel_data_path
    )

    print(
        "AIS vessels loaded:",
        len(vessels),
    )

    # ========================================================
    # 11. LOAD HISTORICAL AIS
    # ========================================================

    print(
        "Loading historical AIS..."
    )

    ais_history = load_ais_history(
        ais_history_path
    )

    # ========================================================
    # RESULTS
    # ========================================================

    results = []

    # ========================================================
    # ENVIRONMENT CACHE
    # ========================================================

    environment_cache = {}

    def environment_cache_key(
        latitude,
        longitude,
    ):
        """
        Open-Meteo environmental models operate on
        kilometer-scale grids. Round coordinates so nearby
        SAR candidates reuse the same environmental request.
        """

        return (
            round(float(latitude), 1),
            round(float(longitude), 1),
        )

    # ========================================================
    # 12. PROCESS EACH SAR CANDIDATE
    # ========================================================

    for candidate_index, candidate in enumerate(
        candidate_features,
        start=1,
    ):

        print("\n")
        print("-" * 60)

        print(
            "Processing candidate",
            candidate_index,
            "/",
            len(candidate_features),
        )

        print(
            "Location:",
            candidate["latitude"],
            candidate["longitude"],
        )

        print("-" * 60)

        # ====================================================
        # ENVIRONMENTAL HINDCAST
        # ====================================================

        print(
            "Running environmental hindcast..."
        )

        environment_key = environment_cache_key(
            candidate["latitude"],
            candidate["longitude"],
        )

        # ----------------------------------------------------
        # USE CACHED ENVIRONMENTAL DATA
        # ----------------------------------------------------

        if environment_key in environment_cache:

            print(
                "Using cached environmental data:",
                environment_key,
            )

            environmental_data = (
                environment_cache[
                    environment_key
                ]
            )

        # ----------------------------------------------------
        # FETCH NEW ENVIRONMENTAL DATA
        # ----------------------------------------------------

        else:

            print(
                "Fetching environmental data:",
                environment_key,
            )

            try:

                environmental_data = fetch_environment(
                    latitude=candidate["latitude"],
                    longitude=candidate["longitude"],
                    observation_time=observation_time,
                )

                environment_cache[
                    environment_key
                ] = environmental_data

                print(
                    "Environmental data loaded successfully."
                )

            except Exception as error:

                print(
                    "\nWARNING: Environmental data request failed."
                )

                print(
                    "Error:",
                    repr(error),
                )

                # ------------------------------------------------
                # FALLBACK TO INCIDENT-LEVEL ENVIRONMENT
                # ------------------------------------------------

                fallback_key = environment_cache_key(
                    latitude,
                    longitude,
                )

                if fallback_key in environment_cache:

                    print(
                        "Using cached incident-level "
                        "environmental data."
                    )

                    environmental_data = (
                        environment_cache[
                            fallback_key
                        ]
                    )

                else:

                    print(
                        "Attempting incident-level "
                        "environmental lookup..."
                    )

                    try:

                        environmental_data = fetch_environment(
                            latitude=latitude,
                            longitude=longitude,
                            observation_time=observation_time,
                        )

                        environment_cache[
                            fallback_key
                        ] = environmental_data

                        print(
                            "Incident-level environmental "
                            "data loaded successfully."
                        )

                    except Exception as fallback_error:

                        print(
                            "WARNING: Incident-level "
                            "environmental lookup also failed."
                        )

                        print(
                            "Error:",
                            repr(fallback_error),
                        )

                        # ------------------------------------------------
                        # NON-FATAL FALLBACK
                        # ------------------------------------------------

                        environmental_data = {
                            "wind_speed_kmh": None,
                            "wind_bearing_deg": None,
                            "current_speed_kmh": None,
                            "current_bearing_deg": None,
                            "wind_timestamp": None,
                            "current_timestamp": None,
                            "wind_provider": None,
                            "current_provider": None,
                            "provider": "UNAVAILABLE",
                            "status": "ENVIRONMENTAL_DATA_UNAVAILABLE",
                        }

        # ====================================================
        # BACKWARD PARTICLE RECONSTRUCTION
        # ====================================================

        particle_lats, particle_lons = backward_particles(
            lat=candidate["latitude"],
            lon=candidate["longitude"],
            hours_back=hours_back,
            environment=environmental_data,
            n=400,
        )

        source_latitude = float(
            np.mean(
                particle_lats
            )
        )

        source_longitude = float(
            np.mean(
                particle_lons
            )
        )

        source_uncertainty_km = float(
            max(
                np.std(
                    particle_lats
                ),
                np.std(
                    particle_lons
                ),
            )
            * 111.0
            * 2.0
        )

        source_time = (
            observation_time
            - timedelta(
                hours=hours_back
            )
        )

        release_window_end = (
            source_time
            + timedelta(
                hours=2
            )
        )

        print(
            "Reconstructed source:",
            round(
                source_latitude,
                5,
            ),
            round(
                source_longitude,
                5,
            ),
        )

        print(
            "Source uncertainty:",
            round(
                source_uncertainty_km,
                2,
            ),
            "km",
        )

        environmental_hindcast = {
            "source_lat": round(
                source_latitude,
                5,
            ),

            "source_lon": round(
                source_longitude,
                5,
            ),

            "uncertainty_radius_km": round(
                source_uncertainty_km,
                2,
            ),

            "particle_count": 400,

            "hours_rewound": hours_back,

            "release_window_start": (
                source_time.isoformat()
            ),

            "release_window_end": (
                release_window_end.isoformat()
            ),

            "environment": environmental_data,
        }

        # ====================================================
        # FIND NEARBY VESSELS
        # ====================================================

        nearby_vessels = rank_vessels(
            vessels=vessels,
            latitude=candidate["latitude"],
            longitude=candidate["longitude"],
            radius_km=radius_km,
        )

        print(
            "Nearby vessels:",
            len(nearby_vessels),
        )

        investigated_vessels = []

        # ====================================================
        # INVESTIGATE EACH VESSEL
        # ====================================================

        for vessel in nearby_vessels:

            # ------------------------------------------------
            # MOTION / SOURCE INVESTIGATION
            # ------------------------------------------------

            investigation = evaluate_vessel_evidence(
                vessel=vessel,
                source_latitude=source_latitude,
                source_longitude=source_longitude,
                hours_back=hours_back,
            )

            # ------------------------------------------------
            # HISTORICAL AIS TRAJECTORY
            # ------------------------------------------------

            timeline = analyze_vessel_timeline(
                history=ais_history,
                mmsi=vessel["mmsi"],
                source_latitude=source_latitude,
                source_longitude=source_longitude,
                observation_time=observation_time,
                source_time=source_time,
            )

            # ------------------------------------------------
            # COMBINE INFORMATION
            # ------------------------------------------------

            vessel_result = {
                **vessel,
                "investigation": investigation,
                "timeline": timeline,
            }

            # =================================================
            # HISTORICAL AIS INDICATORS
            # =================================================

            timeline_gap = timeline.get(
                "ais_gap_hours"
            )

            ais_trajectory_compatible = timeline.get(
                "trajectory_compatible",
                False,
            )

            # =================================================
            # RESPONSIBILITY / PRIORITY SCORE
            # =================================================

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

            # -------------------------------------------------
            # Historical trajectory compatibility
            # -------------------------------------------------

            if ais_trajectory_compatible:

                timeline_component += 10.0

            # -------------------------------------------------
            # AIS gap
            # -------------------------------------------------

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

            # =================================================
            # INVESTIGATION FLAGS
            # =================================================

            flags = list(
                investigation.get(
                    "flags",
                    [],
                )
            )

            # -------------------------------------------------
            # AIS timeline gap
            # -------------------------------------------------

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

            # -------------------------------------------------
            # Historical trajectory
            # -------------------------------------------------

            if ais_trajectory_compatible:

                if (
                    "AIS TRAJECTORY COMPATIBLE"
                    not in flags
                ):

                    flags.append(
                        "AIS TRAJECTORY COMPATIBLE"
                    )

            # =================================================
            # PRIORITY CLASSIFICATION
            # =================================================

            if (
                ais_trajectory_compatible
                and timeline_gap is not None
                and timeline_gap >= 2
            ):

                priority = (
                    "HIGH PRIORITY INVESTIGATION"
                )

            elif (
                investigation[
                    "kinematic_anomaly"
                ]
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

            # =================================================
            # FINAL INVESTIGATION OBJECT
            # =================================================

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

        # ====================================================
        # 13. RANK INVESTIGATED VESSELS
        # ====================================================

        investigated_vessels.sort(
            key=lambda vessel: (
                vessel.get(
                    "responsibility_score",
                    0,
                ),

                vessel.get(
                    "investigation",
                    {},
                ).get(
                    "evidence_score",
                    0,
                ),
            ),

            reverse=True,
        )

        # ====================================================
        # ADD CANDIDATE RESULT
        # ====================================================

        results.append({
            "candidate": candidate,

            "environmental_hindcast": (
                environmental_hindcast
            ),

            "nearby_vessels": (
                investigated_vessels
            ),
        })

    # ========================================================
    # FINAL RESPONSE
    # ========================================================

    # --------------------------------------------------------
    # SAFE CONTRAST SUMMARY
    # --------------------------------------------------------

    if contrast is not None:

        contrast_summary = {
            "min_db": float(
                np.nanmin(
                    contrast
                )
            ),

            "max_db": float(
                np.nanmax(
                    contrast
                )
            ),

            "mean_db": float(
                np.nanmean(
                    contrast
                )
            ),

            "median_db": float(
                np.nanmedian(
                    contrast
                )
            ),
        }

    else:

        contrast_summary = None

    # ========================================================
    # RETURN RESULT
    # ========================================================

    return {
        "status": "success",

        "satellite": {
            "source": "Google Earth Engine",
            "catalog": "COPERNICUS/S1_GRD",
            "mission": "Sentinel-1",
            "product": "Sentinel-1 GRD",

            "bbox": bbox,

            "image_size": [
                int(image_height),
                int(image_width),
            ],

            "adaptive_threshold_db": round(
                float(threshold),
                3,
            ),

            "scene_id": satellite_metadata[
                "scene_id"
            ],

            "acquisition_time": (
                satellite_metadata[
                    "acquisition_time"
                ]
            ),

            "orbit_pass": (
                satellite_metadata[
                    "orbit_pass"
                ]
            ),

            "relative_orbit": (
                satellite_metadata[
                    "relative_orbit"
                ]
            ),

            "instrument_mode": (
                satellite_metadata[
                    "instrument_mode"
                ]
            ),

            "polarization": (
                satellite_metadata[
                    "polarization"
                ]
            ),
        },

        "detection": {
            "candidate_count": len(
                candidate_features
            ),

            "raw_candidate_count": raw_candidate_count,

            "investigated_candidate_count": len(
                candidate_features
            ),

            "candidate_triage_limit": max_investigation_candidates,

            "contrast": contrast_summary,
        },

        "investigation": {
            "hours_back": hours_back,

            "method": (
                "SAR candidate detection + "
                "AIS spatial correlation + "
                "historical AIS timeline analysis + "
                "real modeled wind/current hindcast + "
                "backward particle source reconstruction + "
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

            "environmental_hindcast": {
                "enabled": True,

                "provider": (
                    "Open-Meteo historical wind "
                    "+ marine ocean-current model"
                ),

                "status": (
                    "REAL_MODELED_DATA"
                ),
            },

            "disclaimer": (
                "Investigation indicators are "
                "not legal proof of responsibility."
            ),
        },

        "candidates": results,
    }