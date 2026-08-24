from pipeline import run_pipeline


result = run_pipeline(
    latitude=18.75,
    longitude=72.65,
    start_datetime="2026-08-12T00:00:00Z",
    end_datetime="2026-08-14T23:59:59Z",
    hours_back=48,
    vessel_data_path="data/vessels.csv",
    ais_history_path="data/ais_history.csv",
    observation_time="2026-08-12T22:00:00Z",
    image_output_path="data/pipeline_sentinel1.tif",
    radius_km=100,
    bbox_delta=0.10,
    image_size=800,
    min_candidate_area=1,
)


print("\n======================================")
print("SLICKBACK INVESTIGATION TEST")
print("======================================")

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

    print("\n--------------------------------------")
    print(f"CANDIDATE {i}")
    print("--------------------------------------")

    print(
        "Location:",
        candidate["latitude"],
        candidate["longitude"],
    )

    print(
        "Area:",
        candidate["area_pixels"],
        "pixels",
    )

    print(
        "SAR contrast:",
        candidate["local_contrast_db"],
        "dB",
    )

    print(
        "Nearby vessels:",
        len(vessels),
    )

    # ======================================
    # SHOW ALL VESSELS
    # ======================================

    for rank, vessel in enumerate(
        vessels,
        1,
    ):

        investigation = vessel[
            "investigation"
        ]

        print(
            f"\n  VESSEL #{rank}"
        )

        print(
            "    Name:",
            vessel["name"],
        )

        print(
            "    MMSI:",
            vessel["mmsi"],
        )

        print(
            "    Distance:",
            vessel["distance_km"],
            "km",
        )

        print(
            "    AIS correlation:",
            vessel["correlation_score"],
        )

        print(
            "    Responsibility score:",
            vessel[
                "responsibility_score"
            ],
        )

        print(
            "    AIS gap:",
            investigation[
                "ais_gap_hours"
            ],
            "hours",
        )

        print(
            "    AIS reliability:",
            investigation[
                "ais_reliability"
            ],
        )

        print(
            "    Kinematic anomaly:",
            investigation[
                "kinematic_anomaly"
            ],
        )

        print(
            "    Kinematic score:",
            investigation[
                "kinematic_score"
            ],
        )

        print(
            "    Source distance:",
            investigation[
                "source_distance_km"
            ],
            "km",
        )

        print(
            "    Source trajectory match:",
            investigation[
                "source_trajectory_match"
            ],
        )

        print(
            "    Physically reachable:",
            investigation[
                "physically_reachable"
            ],
        )

        print(
            "    Evidence score:",
            investigation[
                "evidence_score"
            ],
        )

        print(
            "    Intentional indicators:",
            investigation[
                "intentional_indicators"
            ],
        )

        print(
            "    Assessment:",
            investigation[
                "assessment"
            ],
        )

        print(
            "    Flags:",
            investigation[
                "flags"
            ],
        )


print("\n======================================")
print("TEST COMPLETE")
print("======================================")