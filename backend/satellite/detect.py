import numpy as np

from scipy.ndimage import gaussian_filter

from skimage.measure import label, regionprops

from skimage.morphology import (
    binary_opening,
    binary_closing,
    disk
)


def detect_dark_regions(vv_db):
    """
    Detect locally dark regions in Sentinel-1 VV imagery.

    This creates candidate regions only.
    It does NOT classify them as oil.
    """

    valid = vv_db[np.isfinite(vv_db)]

    if valid.size == 0:
        raise ValueError(
            "No valid Sentinel-1 pixels found."
        )

    filled = np.nan_to_num(
        vv_db,
        nan=np.nanmedian(valid)
    )

    # Estimate local sea/background backscatter.
    local_background = gaussian_filter(
        filled,
        sigma=15
    )

    # Negative contrast means darker than surroundings.
    contrast = filled - local_background

    valid_contrast = contrast[
        np.isfinite(vv_db)
    ]

    if valid_contrast.size == 0:
        raise ValueError(
            "No valid contrast values found."
        )

    # Adaptive scene-dependent threshold.
    threshold = np.percentile(
        valid_contrast,
        2
    )

    candidate_mask = (
        contrast < threshold
    )

    # Invalid pixels cannot be candidates.
    candidate_mask[
        ~np.isfinite(vv_db)
    ] = False

    # Remove isolated speckle.
    candidate_mask = binary_opening(
        candidate_mask,
        disk(1)
    )

    # Connect nearby pixels belonging
    # to the same dark structure.
    candidate_mask = binary_closing(
        candidate_mask,
        disk(2)
    )

    return (
        candidate_mask,
        contrast,
        float(threshold)
    )


def extract_candidates(
    candidate_mask,
    min_area=1
):
    """
    Convert dark pixels into connected
    candidate regions.

    This function extracts geometry only.
    It does NOT classify candidates as oil.
    """

    if candidate_mask.ndim != 2:
        raise ValueError(
            "candidate_mask must be a 2D array."
        )

    labeled = label(
        candidate_mask
    )

    regions = regionprops(
        labeled
    )

    candidates = []

    for region in regions:

        if region.area < min_area:
            continue

        min_row, min_col, max_row, max_col = (
            region.bbox
        )

        height = (
            max_row - min_row
        )

        width = (
            max_col - min_col
        )

        if height == 0 or width == 0:
            continue

        aspect_ratio = (
            max(width, height)
            / max(
                min(width, height),
                1
            )
        )

        candidates.append({

            # Connected-component identifier.
            # Used later for extracting
            # Sentinel-1 statistics.
            "label": int(
                region.label
            ),

            "area_pixels": int(
                region.area
            ),

            "centroid_row": round(
                float(region.centroid[0]),
                2
            ),

            "centroid_col": round(
                float(region.centroid[1]),
                2
            ),

            "bbox": [
                int(min_row),
                int(min_col),
                int(max_row),
                int(max_col)
            ],

            "width_pixels": int(
                width
            ),

            "height_pixels": int(
                height
            ),

            "aspect_ratio": round(
                float(aspect_ratio),
                2
            ),

            "eccentricity": round(
                float(region.eccentricity),
                3
            )
        })

    # Largest candidate regions first.
    candidates.sort(
        key=lambda x: x["area_pixels"],
        reverse=True
    )

    return candidates