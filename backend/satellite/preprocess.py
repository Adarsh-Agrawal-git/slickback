import numpy as np
import rasterio


# ============================================================
# LOAD SENTINEL-1
# ============================================================

def load_sentinel1(path):
    """
    Load Sentinel-1 TIFF.

    Supports:
        2D: (height, width)
        3D: (bands, height, width)

    Returns:
        2D float32 VV image.
    """

    with rasterio.open(path) as src:

        data = src.read()

    if data.ndim == 2:

        vv = data

    elif data.ndim == 3:

        if data.shape[0] == 0:

            raise ValueError(
                "Sentinel-1 TIFF contains no bands."
            )

        vv = data[0]

    else:

        raise ValueError(
            f"Unexpected Sentinel-1 TIFF shape: {data.shape}"
        )

    vv = np.asarray(
        vv,
        dtype=np.float32,
    )

    vv[~np.isfinite(vv)] = np.nan

    if not np.any(
        np.isfinite(vv)
    ):

        raise ValueError(
            "Sentinel-1 TIFF contains no valid pixels."
        )

    return vv


# ============================================================
# CONVERT TO dB
# ============================================================

def to_db(vv):
    """
    Convert Sentinel-1 VV data to dB.

    The function automatically determines whether the
    input appears to be linear backscatter or already-dB data.

    Linear backscatter:
        dB = 10 * log10(VV)

    Already-dB data:
        returned unchanged.

    This prevents accidental double conversion.
    """

    vv = np.asarray(
        vv,
        dtype=np.float32,
    )

    valid = np.isfinite(
        vv
    )

    if not np.any(valid):

        raise ValueError(
            "No valid Sentinel-1 values available."
        )

    valid_values = vv[
        valid
    ]

    # --------------------------------------------------------
    # Detect whether values are already in dB.
    #
    # Linear Sentinel-1 backscatter should be positive.
    # Presence of negative values is a strong indication
    # that the image is already represented in dB.
    # --------------------------------------------------------

    negative_fraction = float(
        np.mean(
            valid_values < 0
        )
    )

    if negative_fraction > 0.05:

        print(
            "Sentinel-1 input appears to already be in dB."
        )

        return vv.astype(
            np.float32
        )

    # --------------------------------------------------------
    # Otherwise treat input as linear backscatter.
    # --------------------------------------------------------

    db = np.full_like(
        vv,
        np.nan,
        dtype=np.float32,
    )

    positive = (
        valid
        & (vv > 0)
    )

    db[
        positive
    ] = (
        10.0
        * np.log10(
            vv[positive]
        )
    )

    return db.astype(
        np.float32
    )


# ============================================================
# SPECKLE FILTER
# ============================================================

def remove_speckle(
    image,
    size=3,
):
    """
    Fast median speckle filtering.

    NaN values are temporarily replaced during filtering
    and restored afterwards.
    """

    image = np.asarray(
        image,
        dtype=np.float32,
    )

    if image.ndim != 2:

        raise ValueError(
            f"Expected 2D SAR image, got shape {image.shape}"
        )

    if size < 1:

        raise ValueError(
            "size must be >= 1"
        )

    if size % 2 == 0:

        size += 1

    try:

        from scipy.ndimage import median_filter

    except ImportError:

        print(
            "WARNING: scipy not installed. "
            "Skipping speckle filtering."
        )

        return image

    valid_mask = np.isfinite(
        image
    )

    if not np.any(
        valid_mask
    ):

        return image

    fill_value = float(
        np.nanmedian(
            image
        )
    )

    working = np.where(
        valid_mask,
        image,
        fill_value,
    ).astype(
        np.float32
    )

    filtered = median_filter(
        working,
        size=size,
        mode="nearest",
    )

    filtered[
        ~valid_mask
    ] = np.nan

    return filtered.astype(
        np.float32
    )