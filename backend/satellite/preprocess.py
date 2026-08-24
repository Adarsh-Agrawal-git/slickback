import numpy as np
import tifffile
from scipy.ndimage import median_filter


def load_sentinel1(path):
    """
    Load scientific Sentinel-1 TIFF.

    Supports both common layouts:
        (height, width, bands)
        (bands, height, width)

    Band 0 = VV
    Band 1 = data mask
    """

    data = tifffile.imread(path).astype(np.float32)

    print("\n========== SENTINEL-1 TIFF ==========")
    print("Shape:", data.shape)
    print("Dtype:", data.dtype)
    print("Min:", np.nanmin(data))
    print("Max:", np.nanmax(data))
    print("=====================================\n")

    if data.ndim != 3:
        raise ValueError(
            f"Expected 3D Sentinel-1 TIFF, got shape {data.shape}"
        )

    # Case 1: (height, width, bands)
    if data.shape[-1] == 2:

        vv = data[:, :, 0]
        mask = data[:, :, 1]

    # Case 2: (bands, height, width)
    elif data.shape[0] == 2:

        vv = data[0, :, :]
        mask = data[1, :, :]

    else:
        raise ValueError(
            f"Could not identify VV/dataMask bands. "
            f"Unexpected TIFF shape: {data.shape}"
        )

    vv = vv.astype(np.float32)
    mask = mask.astype(np.float32)

    print("VV valid pixels before mask:",
          np.count_nonzero(np.isfinite(vv)))

    print("Mask values:",
          np.unique(mask)[:10])

    # Apply data mask
    vv[mask <= 0] = np.nan

    print("VV valid pixels after mask:",
          np.count_nonzero(np.isfinite(vv)))

    if not np.any(np.isfinite(vv)):
        raise ValueError(
            "Sentinel-1 TIFF contains no valid VV pixels. "
            "The problem is with the downloaded data/mask."
        )

    return vv


def to_db(vv):
    """
    Convert Sentinel-1 linear backscatter to dB.
    """

    result = np.full_like(
        vv,
        np.nan,
        dtype=np.float32
    )

    valid = (
        np.isfinite(vv)
        & (vv > 0)
    )

    result[valid] = (
        10.0 * np.log10(vv[valid])
    )

    if not np.any(np.isfinite(result)):
        raise ValueError(
            "No valid positive Sentinel-1 VV values "
            "available for dB conversion."
        )

    return result


def remove_speckle(vv_db):
    """
    Simple 3x3 median filter.
    """

    valid_values = vv_db[
        np.isfinite(vv_db)
    ]

    if valid_values.size == 0:
        raise ValueError(
            "Cannot remove speckle: Sentinel-1 image "
            "contains no valid dB pixels."
        )

    fill_value = float(
        np.median(valid_values)
    )

    filled = np.where(
        np.isfinite(vv_db),
        vv_db,
        fill_value
    )

    filtered = median_filter(
        filled,
        size=3
    )

    filtered[
        ~np.isfinite(vv_db)
    ] = np.nan

    return filtered