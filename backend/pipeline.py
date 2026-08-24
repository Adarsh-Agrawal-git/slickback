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
    vessel_data_path,
    image_output_path,
    radius_km,
    bbox_delta,
    image_size,
    min_candidate_area,
):
    """
    Run the real Sentinel-1 -> candidate -> AIS pipeline.

    No vessel identities or spill coordinates are hardcoded.
    """

    # --------------------------------------------------
    # 1. Download REAL Sentinel-1 scientific data
    # --------------------------------------------------

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

    # --------------------------------------------------
    # 2. Load Sentinel-1
    # --------------------------------------------------

    vv = load_sentinel1(
        image_path
    )

    # --------------------------------------------------
    # 3. Preprocess
    # --------------------------------------------------

    vv_db = to_db(vv)

    vv_filtered = remove_speckle(
        vv_db
    )

    # --------------------------------------------------
    # 4. Detect dark regions
    # --------------------------------------------------

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

    # --------------------------------------------------
    # 5. Convert candidate pixels to coordinates
    # --------------------------------------------------

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

    # --------------------------------------------------
    # 6. Extract SAR features
    # --------------------------------------------------

    candidate_features = (
        extract_candidate_features(
            vv_db=vv_filtered,
            candidate_mask=candidate_mask,
            candidates=geographic_candidates,
        )
    )

    # --------------------------------------------------
    # 7. Load AIS data
    # --------------------------------------------------

    vessels = load_vessels(
        vessel_data_path
    )

    # --------------------------------------------------
    # 8. Correlate each candidate with AIS
    # --------------------------------------------------

    results = []

    for candidate in candidate_features:

        nearby_vessels = rank_vessels(
            vessels=vessels,
            latitude=candidate["latitude"],
            longitude=candidate["longitude"],
            radius_km=radius_km,
        )

        results.append({
            "candidate": candidate,
            "nearby_vessels": nearby_vessels,
        })

    # --------------------------------------------------
    # 9. Return complete investigation result
    # --------------------------------------------------

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