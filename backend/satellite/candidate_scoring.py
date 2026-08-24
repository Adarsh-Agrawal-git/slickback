import numpy as np
from scipy.ndimage import binary_dilation


def extract_candidate_features(
    vv_db,
    candidate_mask,
    candidates,
    dilation_pixels=20
):
    """
    Extract SAR features from Sentinel-1 dark-region candidates.

    This function does NOT classify a candidate as oil.

    It only measures properties that can later be used for:
    - oil-spill classification
    - candidate ranking
    - AIS correlation
    - UI explanation

    All measurements are derived from the supplied
    Sentinel-1 image.
    """

    if vv_db.ndim != 2:
        raise ValueError(
            "vv_db must be a 2D Sentinel-1 image."
        )

    if candidate_mask.shape != vv_db.shape:
        raise ValueError(
            "candidate_mask and vv_db must have "
            "the same shape."
        )

    valid_image = np.isfinite(vv_db)

    if not np.any(valid_image):
        raise ValueError(
            "No valid Sentinel-1 pixels available."
        )

    results = []

    for candidate in candidates:

        min_row, min_col, max_row, max_col = (
            candidate["bbox"]
        )

        # Keep the bounding box inside the image.
        min_row = max(0, min_row)
        min_col = max(0, min_col)

        max_row = min(
            vv_db.shape[0],
            max_row
        )

        max_col = min(
            vv_db.shape[1],
            max_col
        )

        if min_row >= max_row or min_col >= max_col:
            continue

        # Candidate region inside its bounding box.
        region_mask = candidate_mask[
            min_row:max_row,
            min_col:max_col
        ]

        image_crop = vv_db[
            min_row:max_row,
            min_col:max_col
        ]

        candidate_pixels = image_crop[
            region_mask
        ]

        candidate_pixels = candidate_pixels[
            np.isfinite(candidate_pixels)
        ]

        if candidate_pixels.size == 0:
            continue

        # --------------------------------------------------
        # Build a local neighbourhood around the candidate.
        # --------------------------------------------------

        local_mask = np.zeros_like(
            candidate_mask,
            dtype=bool
        )

        local_mask[
            min_row:max_row,
            min_col:max_col
        ] = region_mask

        expanded_mask = binary_dilation(
            local_mask,
            iterations=dilation_pixels
        )

        surrounding_mask = (
            expanded_mask
            & ~local_mask
            & valid_image
        )

        surrounding_pixels = vv_db[
            surrounding_mask
        ]

        if surrounding_pixels.size == 0:
            continue

        # --------------------------------------------------
        # Candidate statistics
        # --------------------------------------------------

        candidate_mean = float(
            np.mean(candidate_pixels)
        )

        candidate_median = float(
            np.median(candidate_pixels)
        )

        candidate_std = float(
            np.std(candidate_pixels)
        )

        candidate_min = float(
            np.min(candidate_pixels)
        )

        candidate_max = float(
            np.max(candidate_pixels)
        )

        # --------------------------------------------------
        # Surrounding/background statistics
        # --------------------------------------------------

        surrounding_mean = float(
            np.mean(surrounding_pixels)
        )

        surrounding_median = float(
            np.median(surrounding_pixels)
        )

        surrounding_std = float(
            np.std(surrounding_pixels)
        )

        # --------------------------------------------------
        # Local contrast
        #
        # Positive value means the candidate is darker
        # than its surrounding background.
        # --------------------------------------------------

        local_contrast = (
            surrounding_median
            - candidate_median
        )

        # --------------------------------------------------
        # Add measured SAR features to the candidate.
        # --------------------------------------------------

        result = {
            **candidate,

            "candidate_mean_db": round(
                candidate_mean,
                3
            ),

            "candidate_median_db": round(
                candidate_median,
                3
            ),

            "candidate_std_db": round(
                candidate_std,
                3
            ),

            "candidate_min_db": round(
                candidate_min,
                3
            ),

            "candidate_max_db": round(
                candidate_max,
                3
            ),

            "surrounding_mean_db": round(
                surrounding_mean,
                3
            ),

            "surrounding_median_db": round(
                surrounding_median,
                3
            ),

            "surrounding_std_db": round(
                surrounding_std,
                3
            ),

            "local_contrast_db": round(
                local_contrast,
                3
            ),

            "candidate_pixel_count": int(
                candidate_pixels.size
            ),

            "surrounding_pixel_count": int(
                surrounding_pixels.size
            )
        }

        results.append(result)

    return results