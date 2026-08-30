from pathlib import Path

import numpy as np
import rasterio
from PIL import Image


def create_sentinel1_preview(
    input_path,
    output_path,
):
    """
    Convert the actual Sentinel-1 GeoTIFF used by the
    analysis pipeline into a browser-friendly PNG preview.

    The pixel data is normalized independently for display.
    The original TIFF is not modified.
    """

    input_path = Path(input_path)
    output_path = Path(output_path)

    if not input_path.exists():
        raise FileNotFoundError(
            f"Sentinel-1 image not found: {input_path}"
        )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with rasterio.open(
        input_path
    ) as dataset:

        band = dataset.read(
            1
        ).astype(
            np.float32
        )

    finite = np.isfinite(
        band
    )

    if not finite.any():
        raise ValueError(
            "Sentinel-1 image contains no valid pixels."
        )

    valid = band[
        finite
    ]

    low = np.percentile(
        valid,
        2
    )

    high = np.percentile(
        valid,
        98
    )

    if high <= low:
        high = low + 1.0

    normalized = (
        (band - low)
        / (high - low)
        * 255.0
    )

    normalized = np.clip(
        normalized,
        0,
        255,
    )

    normalized[
        ~finite
    ] = 0

    image = Image.fromarray(
        normalized.astype(
            np.uint8
        ),
        mode="L",
    )

    image.save(
        output_path,
        format="PNG",
    )

    return str(
        output_path
    )