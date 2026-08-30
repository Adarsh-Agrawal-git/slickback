import numpy as np

from scipy.ndimage import (
    median_filter,
    binary_opening,
    binary_closing,
)

from skimage.measure import (
    label,
    regionprops,
)

from skimage.morphology import disk


# ============================================================
# DARK REGION DETECTION
# ============================================================

def detect_dark_regions(vv_db):
    """
    Detect locally dark regions in Sentinel-1 VV imagery.

    This produces potential SAR dark-region candidates.
    It does NOT classify them as oil.

    Pipeline:

        VV dB
          ↓
        Local median background
          ↓
        Local darkness
          ↓
        Adaptive threshold
          ↓
        Morphological grouping
          ↓
        Candidate mask
    """

    vv_db = np.asarray(
        vv_db,
        dtype=np.float32,
    )

    if vv_db.ndim != 2:
        raise ValueError(
            "vv_db must be a 2D array."
        )

    valid_mask = np.isfinite(
        vv_db
    )

    if not np.any(valid_mask):
        raise ValueError(
            "No valid Sentinel-1 pixels found."
        )

    valid_values = vv_db[
        valid_mask
    ]

    fill_value = float(
        np.median(valid_values)
    )

    filled = np.where(
        valid_mask,
        vv_db,
        fill_value,
    ).astype(
        np.float32
    )

    # --------------------------------------------------------
    # Local background
    # --------------------------------------------------------

    local_background = median_filter(
        filled,
        size=31,
        mode="nearest",
    )

    # --------------------------------------------------------
    # Positive darkness:
    #
    # positive = darker than local background
    # --------------------------------------------------------

    darkness = (
        local_background
        - filled
    ).astype(
        np.float32
    )

    darkness[
        ~valid_mask
    ] = np.nan

    valid_darkness = darkness[
        valid_mask
    ]

    if valid_darkness.size == 0:
        raise ValueError(
            "No valid darkness values found."
        )

    # --------------------------------------------------------
    # Scene statistics
    # --------------------------------------------------------

    p50 = float(
        np.percentile(
            valid_darkness,
            50,
        )
    )

    p90 = float(
        np.percentile(
            valid_darkness,
            90,
        )
    )

    p95 = float(
        np.percentile(
            valid_darkness,
            95,
        )
    )

    p97 = float(
        np.percentile(
            valid_darkness,
            97,
        )
    )

    p99 = float(
        np.percentile(
            valid_darkness,
            99,
        )
    )

    # --------------------------------------------------------
    # Adaptive threshold
    #
    # P95 worked for this real Sentinel-1 scene and
    # provides a reasonably conservative candidate set.
    # --------------------------------------------------------

    threshold = max(
        2.0,
        min(
            p95,
            8.0,
        ),
    )

    # --------------------------------------------------------
    # Initial candidate mask
    # --------------------------------------------------------

    candidate_mask = (
        darkness >= threshold
    )

    candidate_mask[
        ~valid_mask
    ] = False

    # --------------------------------------------------------
    # Remove isolated single-pixel noise.
    # --------------------------------------------------------

    candidate_mask = binary_opening(
        candidate_mask,
        structure=disk(1),
    )

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # Use a stronger closing operation to connect nearby
    # dark pixels that belong to the same structure.
    #
    # Our previous disk(2) left the 113 pixels fragmented
    # into mostly 5-pixel components.
    # --------------------------------------------------------

    candidate_mask = binary_closing(
        candidate_mask,
        structure=disk(4),
    )

    # --------------------------------------------------------
    # Connected-component filtering
    # --------------------------------------------------------

    labeled = label(
        candidate_mask
    )

    cleaned_mask = np.zeros(
        candidate_mask.shape,
        dtype=bool,
    )

    for region in regionprops(
        labeled
    ):

        if region.area >= 10:

            cleaned_mask[
                labeled == region.label
            ] = True

    # --------------------------------------------------------
    # Debug information
    # --------------------------------------------------------

    print()
    print(
        "SAR DARKNESS STATISTICS"
    )

    print(
        "P50:",
        round(p50, 3),
    )

    print(
        "P90:",
        round(p90, 3),
    )

    print(
        "P95:",
        round(p95, 3),
    )

    print(
        "P97:",
        round(p97, 3),
    )

    print(
        "P99:",
        round(p99, 3),
    )

    print(
        "Adaptive threshold:",
        round(threshold, 3),
    )

    print(
        "Candidate pixels:",
        int(
            cleaned_mask.sum()
        ),
    )

    return (
        cleaned_mask,
        darkness,
        float(threshold),
    )


# ============================================================
# CANDIDATE EXTRACTION
# ============================================================

def extract_candidates(
    candidate_mask,
    min_area=10,
):
    """
    Extract connected SAR dark-region candidates.

    Geometry only.
    This function does NOT classify candidates as oil.
    """

    candidate_mask = np.asarray(
        candidate_mask,
        dtype=bool,
    )

    if candidate_mask.ndim != 2:
        raise ValueError(
            "candidate_mask must be a 2D array."
        )

    if min_area < 1:
        raise ValueError(
            "min_area must be >= 1."
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
            max_row
            - min_row
        )

        width = (
            max_col
            - min_col
        )

        if (
            height <= 0
            or width <= 0
        ):
            continue

        aspect_ratio = (
            max(
                width,
                height,
            )
            /
            max(
                min(
                    width,
                    height,
                ),
                1,
            )
        )

        candidates.append({

            "label": int(
                region.label
            ),

            "area_pixels": int(
                region.area
            ),

            "centroid_row": round(
                float(
                    region.centroid[0]
                ),
                2,
            ),

            "centroid_col": round(
                float(
                    region.centroid[1]
                ),
                2,
            ),

            "bbox": [
                int(min_row),
                int(min_col),
                int(max_row),
                int(max_col),
            ],

            "width_pixels": int(
                width
            ),

            "height_pixels": int(
                height
            ),

            "aspect_ratio": round(
                float(
                    aspect_ratio
                ),
                2,
            ),

            "eccentricity": round(
                float(
                    region.eccentricity
                ),
                3,
            ),

            "solidity": round(
                float(
                    region.solidity
                ),
                3,
            ),

            "extent": round(
                float(
                    region.extent
                ),
                3,
            ),

            "orientation": round(
                float(
                    region.orientation
                ),
                4,
            ),
        })

    candidates.sort(
        key=lambda candidate: (
            candidate["area_pixels"],
            candidate["solidity"],
        ),
        reverse=True,
    )

    return candidates