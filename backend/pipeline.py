from investigation import evaluate_vessel_evidence

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
    image_output_path,
    radius_km,
    bbox_delta,
    image_size,
    min_candidate_area,
):
    """
    Run the complete SlickBack investigation pipeline.

    Flow:

        Sentinel-1
            ↓
        Preprocessing
            ↓
        Dark-region detection
            ↓
        Candidate extraction
            ↓
        Geographic coordinates
            ↓
        SAR features
            ↓
        AIS correlation
            ↓
        Vessel investigation
            ↓
        Evidence / assessment
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

    vv_db = to_db(vv)

    vv_filtered = remove_speckle(
        vv_db
    )

    # ==================================================
    # 4. DETECT DARK REGIONS
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
    # 5. CONVERT PIXELS TO LAT/LON
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

    candidate_features = extract_candidate_features(
        vv_db=vv_filtered,
        candidate_mask=candidate_mask,
        candidates=geographic_candidates,
    )

    # ==================================================
    # 7. LOAD AIS
    # ==================================================

    vessels = load_vessels(
        vessel_data_path
    )

    # ==================================================
    # 8. AIS + INVESTIGATION
    # ==================================================

    results = []

    for candidate in candidate_features:

        nearby_vessels = rank_vessels(
            vessels=vessels,
            latitude=candidate["latitude"],
            longitude=candidate["longitude"],
            radius_km=radius_km,
        )

        investigated_vessels = []

        for vessel in nearby_vessels:

            evidence = evaluate_vessel_evidence(
                vessel=vessel,
                source_latitude=candidate["latitude"],
                source_longitude=candidate["longitude"],
                hours_back=hours_back,
            )

            # Combine the existing AIS correlation
            # with the new investigation evidence.
            responsibility_score = (
                0.40
                * vessel["correlation_score"]
                * 100.0
                +
                0.60
                * evidence["evidence_score"]
            )

            investigated_vessels.append({
                **vessel,

                "investigation": evidence,

                "responsibility_score": round(
                    responsibility_score,
                    1,
                ),
            })

        # Rank using the final investigation score.
        investigated_vessels.sort(
            key=lambda vessel: (
                vessel["responsibility_score"],
                vessel["correlation_score"],
            ),
            reverse=True,
        )

        results.append({
            "candidate": candidate,
            "nearby_vessels": investigated_vessels,
        })

    # ==================================================
    # 9. RETURN COMPLETE RESULT
    # ==================================================

    return {
        "status": "success",

        "satellite": {
            "source": "Copernicus Data Space",
            "mission": "Sentinel-1",
            "product": "sentinel-1-grd",

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

        "candidates": results,
    }