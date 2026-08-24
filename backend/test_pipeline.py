from pipeline import run_pipeline


result = run_pipeline(
    latitude=18.75,
    longitude=72.65,
    start_datetime="2026-08-01T00:00:00Z",
    end_datetime="2026-08-24T23:59:59Z",
    vessel_data_path="data/vessels.csv",
    image_output_path="data/pipeline_sentinel1.tif",
    radius_km=100,
    bbox_delta=0.10,
    image_size=800,
    min_candidate_area=1,
)


print("\nSTATUS:")
print(result["status"])

print("\nCANDIDATES:")
print(
    result["detection"]["candidate_count"]
)

for i, item in enumerate(
    result["candidates"][:5],
    1,
):

    candidate = item["candidate"]
    vessels = item["nearby_vessels"]

    print(
        f"\nCandidate {i}"
    )

    print(
        "  Location:",
        candidate["latitude"],
        candidate["longitude"],
    )

    print(
        "  Area:",
        candidate["area_pixels"],
    )

    print(
        "  SAR contrast:",
        candidate["local_contrast_db"],
        "dB",
    )

    print(
        "  Nearby vessels:",
        len(vessels),
    )

    if vessels:

        vessel = vessels[0]

        print(
            "  Top vessel:",
            vessel["name"],
        )

        print(
            "  MMSI:",
            vessel["mmsi"],
        )

        print(
            "  Distance:",
            vessel["distance_km"],
            "km",
        )

        print(
            "  Correlation:",
            vessel["correlation_score"],
        )