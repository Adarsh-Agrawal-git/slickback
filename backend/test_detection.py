import numpy as np
import matplotlib.pyplot as plt

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


# ---------------------------------------------------------
# 1. Download REAL Sentinel-1 data
# ---------------------------------------------------------

result = download_sentinel1_scientific(
    latitude=18.75,
    longitude=72.65,
    start_datetime="2026-08-12T00:00:00Z",
    end_datetime="2026-08-14T23:59:59Z",
)

image_path = result["path"]
bbox = result["bbox"]


print("\nSENTINEL-1 ACQUISITION")
print("----------------------")
print("Image:", image_path)
print("BBOX:", bbox)


# ---------------------------------------------------------
# 2. Load SAR data
# ---------------------------------------------------------

vv = load_sentinel1(
    image_path
)


# ---------------------------------------------------------
# 3. Convert to dB
# ---------------------------------------------------------

vv_db = to_db(
    vv
)


# ---------------------------------------------------------
# 4. Speckle reduction
# ---------------------------------------------------------

vv_filtered = remove_speckle(
    vv_db
)


# ---------------------------------------------------------
# 5. Detect dark candidate regions
# ---------------------------------------------------------

candidate_mask, contrast, threshold = detect_dark_regions(
    vv_filtered
)


# ---------------------------------------------------------
# 6. Extract connected regions
# ---------------------------------------------------------

candidates = extract_candidates(
    candidate_mask,
    min_area=10
)


# ---------------------------------------------------------
# 7. Print scene information
# ---------------------------------------------------------

print("\nSCENE STATISTICS")
print("----------------")
print("IMAGE SIZE:", vv.shape)

print(
    "VV dB RANGE:",
    np.nanmin(vv_filtered),
    "to",
    np.nanmax(vv_filtered)
)

print(
    "ADAPTIVE CONTRAST THRESHOLD:",
    round(threshold, 3),
    "dB"
)

print(
    "CANDIDATE REGIONS:",
    len(candidates)
)


# ---------------------------------------------------------
# 8. Convert candidate pixels → latitude/longitude
# ---------------------------------------------------------

print("\nCANDIDATE LOCATIONS")
print("-------------------")


image_height, image_width = vv.shape


for i, candidate in enumerate(
    candidates[:10],
    1
):

    location = pixel_to_latlon(
        row=candidate["centroid_row"],
        col=candidate["centroid_col"],
        image_height=image_height,
        image_width=image_width,
        bbox=bbox,
    )

    print(
        f"\nCandidate {i}:"
    )

    print(
        "  Area:",
        candidate["area_pixels"],
        "pixels"
    )

    print(
        "  Centroid pixel:",
        (
            candidate["centroid_row"],
            candidate["centroid_col"]
        )
    )

    print(
        "  Latitude:",
        round(location["latitude"], 6)
    )

    print(
        "  Longitude:",
        round(location["longitude"], 6)
    )

    print(
        "  Aspect ratio:",
        candidate["aspect_ratio"]
    )

    print(
        "  Eccentricity:",
        candidate["eccentricity"]
    )


# ---------------------------------------------------------
# 9. Visualization
# ---------------------------------------------------------

plt.figure(
    figsize=(8, 8)
)

plt.imshow(
    vv_filtered,
    cmap="gray"
)

plt.contour(
    candidate_mask,
    levels=[0.5]
)

plt.title(
    "Sentinel-1 VV — Candidate Dark Regions"
)

plt.axis("off")

plt.show()