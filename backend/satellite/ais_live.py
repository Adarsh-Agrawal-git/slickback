import csv
import os
from pathlib import Path
from datetime import datetime, timezone

import requests


# ============================================================
# CONFIG
# ============================================================

OPENWATERS_URL = (
    "https://ais.openwaters.io/v1/vessels"
)


# ============================================================
# HELPERS
# ============================================================

def _utc_now():
    return datetime.now(timezone.utc)


def _parse_timestamp(value):
    if not value:
        return _utc_now().isoformat()

    try:
        dt = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt.astimezone(
            timezone.utc
        ).isoformat()

    except Exception:
        return _utc_now().isoformat()


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ============================================================
# BOUNDING BOX
# ============================================================

def _build_bbox(
    latitude,
    longitude,
    radius_km,
):
    """
    Build a geographic bounding box around
    the requested coordinate.

    Returns:
        [[[south, west], [north, east]]]
    """

    latitude = float(latitude)
    longitude = float(longitude)
    radius_km = float(radius_km)

    lat_delta = radius_km / 111.0

    longitude_scale = max(
        0.1,
        abs(__import__("math").cos(
            __import__("math").radians(
                latitude
            )
        ))
    )

    lon_delta = (
        radius_km
        / (
            111.0
            * longitude_scale
        )
    )

    south = max(
        -90.0,
        latitude - lat_delta
    )

    north = min(
        90.0,
        latitude + lat_delta
    )

    west = max(
        -180.0,
        longitude - lon_delta
    )

    east = min(
        180.0,
        longitude + lon_delta
    )

    return [
        [
            south,
            west,
        ],
        [
            north,
            east,
        ],
    ]


# ============================================================
# FETCH LIVE AIS
# ============================================================

def fetch_live_vessels(
    latitude,
    longitude,
    radius_km=50,
    timeout_seconds=30,
):
    """
    Fetch currently visible AIS vessels from
    the Open Waters AIS endpoint.

    The provider returns GeoJSON features.
    """

    bbox = _build_bbox(
        latitude,
        longitude,
        radius_km,
    )

    south = bbox[0][0]
    west = bbox[0][1]
    north = bbox[1][0]
    east = bbox[1][1]

    bbox_parameter = (
        f"{south},{west},{north},{east}"
    )

    print()
    print(
        "LIVE AIS PROVIDER: OPEN WATERS"
    )

    print(
        "Bounding box:",
        bbox_parameter,
    )

    try:

        response = requests.get(
            OPENWATERS_URL,
            params={
                "bbox": bbox_parameter,
            },
            timeout=timeout_seconds,
        )

        response.raise_for_status()

        payload = response.json()

    except Exception as error:

        raise RuntimeError(
            "Open Waters AIS request failed: "
            + str(error)
        )

    features = payload.get(
        "features",
        []
    )

    vessels = []

    for feature in features:

        if not isinstance(
            feature,
            dict
        ):
            continue

        geometry = feature.get(
            "geometry",
            {}
        )

        properties = feature.get(
            "properties",
            {}
        )

        if not isinstance(
            geometry,
            dict
        ):
            continue

        if not isinstance(
            properties,
            dict
        ):
            continue

        coordinates = geometry.get(
            "coordinates",
            []
        )

        if (
            not isinstance(
                coordinates,
                list
            )
            or len(coordinates) < 2
        ):
            continue

        longitude_value = _safe_float(
            coordinates[0],
            None,
        )

        latitude_value = _safe_float(
            coordinates[1],
            None,
        )

        if (
            latitude_value is None
            or longitude_value is None
        ):
            continue

        mmsi = properties.get(
            "mmsi",
            feature.get("id"),
        )

        if mmsi is None:
            continue

        mmsi = str(mmsi)

        speed_knots = _safe_float(
            properties.get(
                "sog",
                0,
            )
        )

        heading = _safe_float(
            properties.get(
                "heading",
                properties.get(
                    "cog",
                    0,
                ),
            )
        )

        timestamp = _parse_timestamp(
            properties.get(
                "seen"
            )
        )

        name = (
            properties.get(
                "name"
            )
            or properties.get(
                "ship_name"
            )
            or mmsi
        )

        vessels.append({

            "mmsi": mmsi,

            "name": str(
                name
            ),

            "lat": latitude_value,

            "lon": longitude_value,

            "speed_knots": speed_knots,

            "heading": heading,

            "message_type": str(
                properties.get(
                    "msg_type",
                    "PositionReport",
                )
            ),

            "ais_timestamp": timestamp,

            "received_at": _utc_now().isoformat(),

            # Derived fields expected by
            # the SlickBack correlation layer.
            "ais_reliability": 1.0,

            "ais_gap_hours": 0.0,

            "sar_support": 0.0,
        })

    # Remove duplicate MMSIs.
    unique = {}

    for vessel in vessels:

        unique[
            vessel["mmsi"]
        ] = vessel

    vessels = list(
        unique.values()
    )

    print(
        "Live vessels received:",
        len(vessels),
    )

    return vessels


# ============================================================
# WRITE VESSEL CSV
# ============================================================

def save_vessels(
    vessels,
    path,
):
    """
    Save normalized live AIS data in the format
    expected by the SlickBack AIS analysis layer.
    """

    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = [
        "mmsi",
        "name",
        "lat",
        "lon",
        "speed_knots",
        "heading",
        "message_type",
        "ais_timestamp",
        "received_at",
        "ais_reliability",
        "ais_gap_hours",
        "sar_support",
    ]

    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for vessel in vessels:

            writer.writerow({
                field: vessel.get(
                    field,
                    "",
                )
                for field in fieldnames
            })

    print(
        "Live AIS saved:",
        path,
    )


# ============================================================
# MAIN REFRESH FUNCTION
# ============================================================

def refresh_live_ais(
    latitude,
    longitude,
    radius_km,
    vessels_path,
    history_path=None,
    duration_seconds=30,
):
    """
    Refresh the current live AIS vessel dataset.

    Open Waters provides a current vessel snapshot,
    therefore duration_seconds is retained for API
    compatibility but is not used as a streaming wait.
    """

    print()
    print(
        "============================================================"
    )

    print(
        "REFRESHING LIVE AIS"
    )

    print(
        "============================================================"
    )

    vessels = fetch_live_vessels(
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        timeout_seconds=30,
    )

    save_vessels(
        vessels,
        vessels_path,
    )

    return {

        "enabled": True,

        "available": True,

        "status": (
            "success"
            if vessels
            else "no_vessels"
        ),

        "provider": "Open Waters",

        "vessels_received": len(
            vessels
        ),

        "latitude": float(
            latitude
        ),

        "longitude": float(
            longitude
        ),

        "radius_km": float(
            radius_km
        ),

        "vessels": vessels,
    }