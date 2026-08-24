from pipeline import run_pipeline


result = run_pipeline(
    latitude=18.75,
    longitude=72.65,
    start_datetime="2026-08-12T00:00:00Z",
    end_datetime="2026-08-14T23:59:59Z",
    hours_back=48,
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

        investigation = vessel[
            "investigation"
        ]

        print(
            "\n  --- TOP VESSEL ---"
        )

        print(
            "  Name:",
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
            "  AIS correlation:",
            vessel["correlation_score"],
        )

        print(
            "  Responsibility score:",
            vessel[
                "responsibility_score"
            ],
        )

        print(
            "\n  --- INVESTIGATION ---"
        )

        print(
            "  Historical estimated position:",
            investigation[
                "estimated_historical_position"
            ],
        )

        print(
            "  Source distance:",
            investigation[
                "source_distance_km"
            ],
            "km",
        )

        print(
            "  Source trajectory match:",
            investigation[
                "source_trajectory_match"
            ],
        )

        print(
            "  AIS gap:",
            investigation[
                "ais_gap_hours"
            ],
            "hours",
        )

        print(
            "  Kinematic anomaly:",
            investigation[
                "kinematic_anomaly"
            ],
        )

        print(
            "  Kinematic score:",
            investigation[
                "kinematic_score"
            ],
        )

        print(
            "  AIS reliability:",
            investigation[
                "ais_reliability"
            ],
        )

        print(
            "  Evidence score:",
            investigation[
                "evidence_score"
            ],
        )

        print(
            "  Assessment:",
            investigation[
                "assessment"
            ],
        )

        print(
            "  Flags:",
            investigation[
                "flags"
            ],
        )