import asyncio
import json
import os
from datetime import datetime, timezone

import websockets


AISSTREAM_URL = "wss://stream.aisstream.io/v0/stream"


# ============================================================
# HELPERS
# ============================================================

def _get_api_key():
    api_key = os.getenv("AISSTREAM_API_KEY")

    if not api_key:
        raise RuntimeError(
            "AISSTREAM_API_KEY is not set."
        )

    return api_key


def _build_bbox(
    latitude,
    longitude,
    radius_km,
):
    """
    Approximate geographic bounding box around a center point.
    """

    lat_delta = radius_km / 111.0

    lon_scale = max(
        abs(__import__("math").cos(
            __import__("math").radians(latitude)
        )),
        0.2,
    )

    lon_delta = (
        radius_km
        / (111.0 * lon_scale)
    )

    return [
        [
            latitude - lat_delta,
            longitude - lon_delta,
        ],
        [
            latitude + lat_delta,
            longitude + lon_delta,
        ],
    ]


def _decode_message(raw_message):
    """
    AISStream sends binary WebSocket frames containing UTF-8 JSON.
    """

    if isinstance(raw_message, bytes):
        raw_message = raw_message.decode(
            "utf-8",
            errors="replace",
        )

    return json.loads(raw_message)


def _extract_position(event):
    """
    Extract a normalized vessel observation from supported
    AIS position message types.

    Returns None when the event is not a usable position report.
    """

    message_type = event.get(
        "MessageType"
    )

    metadata = event.get(
        "MetaData",
        {},
    )

    message = event.get(
        "Message",
        {},
    )

    position = None

    if message_type == "PositionReport":
        position = message.get(
            "PositionReport"
        )

    elif message_type == "StandardClassBPositionReport":
        position = message.get(
            "StandardClassBPositionReport"
        )

    elif message_type == "ExtendedClassBPositionReport":
        position = message.get(
            "ExtendedClassBPositionReport"
        )

    if not isinstance(position, dict):
        return None

    # --------------------------------------------------------
    # MMSI
    # --------------------------------------------------------

    mmsi = (
        metadata.get("MMSI")
        or position.get("UserID")
    )

    if mmsi is None:
        return None

    # --------------------------------------------------------
    # LAT / LON
    # --------------------------------------------------------

    latitude = (
        metadata.get("Latitude")
        if metadata.get("Latitude") is not None
        else position.get("Latitude")
    )

    longitude = (
        metadata.get("Longitude")
        if metadata.get("Longitude") is not None
        else position.get("Longitude")
    )

    if latitude is None or longitude is None:
        return None

    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (
        TypeError,
        ValueError,
    ):
        return None

    if not (
        -90.0 <= latitude <= 90.0
        and -180.0 <= longitude <= 180.0
    ):
        return None

    # --------------------------------------------------------
    # SPEED
    # --------------------------------------------------------

    speed_knots = position.get(
        "Sog"
    )

    if speed_knots is None:
        speed_knots = 0.0

    try:
        speed_knots = float(
            speed_knots
        )
    except (
        TypeError,
        ValueError,
    ):
        speed_knots = 0.0

    # --------------------------------------------------------
    # COURSE
    # --------------------------------------------------------

    heading = position.get(
        "TrueHeading"
    )

    if heading is None:
        heading = position.get(
            "Cog"
        )

    if heading is None:
        heading = 0.0

    try:
        heading = float(
            heading
        )
    except (
        TypeError,
        ValueError,
    ):
        heading = 0.0

    # --------------------------------------------------------
    # SHIP NAME
    # --------------------------------------------------------

    ship_name = (
        metadata.get("ShipName")
        or "UNKNOWN"
    )

    if isinstance(
        ship_name,
        str,
    ):
        ship_name = ship_name.strip()

    # --------------------------------------------------------
    # AIS TIMESTAMP
    # --------------------------------------------------------

    timestamp = position.get(
        "Timestamp"
    )

    if timestamp is not None:

        try:
            timestamp = int(
                timestamp
            )
        except (
            TypeError,
            ValueError,
        ):
            timestamp = None

    # --------------------------------------------------------
    # NORMALIZED RESULT
    # --------------------------------------------------------

    return {
        "mmsi": str(mmsi),
        "name": ship_name,
        "lat": latitude,
        "lon": longitude,
        "speed_knots": speed_knots,
        "heading": heading,
        "message_type": message_type,
        "ais_timestamp": timestamp,
        "received_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }


# ============================================================
# ASYNC COLLECTOR
# ============================================================

async def _collect_live_ais(
    latitude,
    longitude,
    radius_km,
    duration_seconds,
):
    api_key = _get_api_key()

    bbox = _build_bbox(
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
    )

    print("\n")
    print("=" * 60)
    print("LIVE AIS STREAM")
    print("=" * 60)

    print(
        "Center:",
        latitude,
        longitude,
    )

    print(
        "Radius:",
        radius_km,
        "km",
    )

    print(
        "Bounding box:",
        bbox,
    )

    print(
        "Duration:",
        duration_seconds,
        "seconds",
    )

    print(
        "AISStream URL:",
        AISSTREAM_URL,
    )

    print("=" * 60)

    subscription = {
    "APIKey": api_key,
    "BoundingBoxes": [
        bbox
    ],
   }
    vessels = {}

    try:

        print(
            "Connecting to AISStream..."
        )

        # Enable permessage-deflate as recommended by AISStream.
        async with websockets.connect(
            AISSTREAM_URL,
            compression="deflate",
            ping_interval=20,
            ping_timeout=20,
            close_timeout=5,
            max_size=4 * 1024 * 1024,
        ) as websocket:

            print(
                "AISStream WebSocket connected."
            )

            await websocket.send(
                json.dumps(
                    subscription
                )
            )

            print(
                "AIS subscription sent."
            )

            start_time = (
                asyncio.get_running_loop()
                .time()
            )

            while True:

                elapsed = (
                    asyncio.get_running_loop()
                    .time()
                    - start_time
                )

                if elapsed >= duration_seconds:
                    print(
                        "AIS collection duration reached."
                    )
                    break

                remaining = max(
                    1.0,
                    duration_seconds - elapsed,
                )

                try:

                    raw_message = await asyncio.wait_for(
                        websocket.recv(),
                        timeout=min(
                            10.0,
                            remaining,
                        ),
                    )

                except asyncio.TimeoutError:

                    print(
                        "AIS receive timeout; "
                        "connection still open."
                    )

                    continue

                except websockets.ConnectionClosed as error:

                    print(
                        "AISStream connection closed:"
                    )

                    print(
                        "  code:",
                        error.code,
                    )

                    print(
                        "  reason:",
                        error.reason,
                    )

                    break

                except Exception as error:

                    print(
                        "AIS receive error:",
                        repr(error),
                    )

                    break

                # ------------------------------------------------
                # DECODE
                # ------------------------------------------------

                try:

                    event = _decode_message(
                        raw_message
                    )

                except Exception as error:

                    print(
                        "AIS JSON decode error:",
                        repr(error),
                    )

                    continue

                message_type = event.get(
                    "MessageType"
                )

                print(
                    "AIS MESSAGE TYPE:",
                    message_type,
                )

                # ------------------------------------------------
                # SUBSCRIPTION CONFIRMATION
                # ------------------------------------------------

                if message_type == "SubscriptionConfirmation":

                    confirmation = event.get(
                        "Message",
                        {},
                    )

                    print(
                        "AIS subscription confirmed."
                    )

                    print(
                        "Compression:",
                        confirmation.get(
                            "CompressionEnabled"
                        ),
                    )

                    continue

                # ------------------------------------------------
                # POSITION MESSAGE
                # ------------------------------------------------

                vessel = _extract_position(
                    event
                )

                if vessel is None:
                    continue

                mmsi = vessel["mmsi"]

                vessels[mmsi] = vessel

                print(
                    "AIS VESSEL:",
                    vessel["mmsi"],
                    vessel["name"],
                    vessel["lat"],
                    vessel["lon"],
                    vessel["speed_knots"],
                    "knots",
                )

    except Exception as error:

        print(
            "\n========== AIS STREAM ERROR =========="
        )

        print(
            repr(error)
        )

        print(
            "======================================"
        )

    print("\n")
    print(
        "Live vessels received:",
        len(vessels),
    )

    print(
        "=" * 60
    )

    return list(
        vessels.values()
    )


# ============================================================
# PUBLIC FUNCTION
# ============================================================

def refresh_live_ais(
    latitude,
    longitude,
    radius_km,
    vessels_path=None,
    history_path=None,
    duration_seconds=60,
):
    """
    Collect live AIS observations.

    This function intentionally keeps the same public interface
    used by main.py.
    """

    vessels = asyncio.run(
        _collect_live_ais(
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
            duration_seconds=duration_seconds,
        )
    )

    # --------------------------------------------------------
    # Optional persistence
    # --------------------------------------------------------

    if vessels_path:
        try:
            import csv

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
            ]

            with open(
                vessels_path,
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
                            field
                        )
                        for field in fieldnames
                    })

            print(
                "Live AIS saved to:",
                vessels_path,
            )

        except Exception as error:

            print(
                "WARNING: could not save "
                "live AIS vessels:",
                repr(error),
            )

    print(
        "LIVE AIS REFRESH COMPLETE:"
    )

    print(
        vessels
    )

    return vessels