from pathlib import Path
from datetime import datetime, timezone

import ee
import requests
from google.oauth2 import service_account


# ============================================================
# EARTH ENGINE CONFIG
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

PROJECT_ID = "slickback-507020"
KEY_FILE = BASE_DIR / "slickback-earthengine.json"

EE_SCOPE = [
    "https://www.googleapis.com/auth/earthengine",
    "https://www.googleapis.com/auth/cloud-platform",
]


# ============================================================
# EARTH ENGINE INITIALIZATION
# ============================================================

_EE_INITIALIZED = False


def initialize_earth_engine():
    global _EE_INITIALIZED

    if _EE_INITIALIZED:
        return

    if not KEY_FILE.exists():
        raise FileNotFoundError(
            f"Earth Engine service account key not found: {KEY_FILE}"
        )

    credentials = service_account.Credentials.from_service_account_file(
        str(KEY_FILE),
        scopes=EE_SCOPE,
    )

    ee.Initialize(
        credentials=credentials,
        project=PROJECT_ID,
    )

    _EE_INITIALIZED = True

    print("Earth Engine authentication: OK")


# ============================================================
# BBOX
# ============================================================

def build_bbox(latitude, longitude, delta):
    if delta <= 0:
        raise ValueError("delta must be greater than zero.")

    return [
        longitude - delta,
        latitude - delta,
        longitude + delta,
        latitude + delta,
    ]


# ============================================================
# DATETIME HELPERS
# ============================================================

def _parse_datetime(value):
    """
    Convert ISO datetime into a timezone-aware datetime.
    """

    if isinstance(value, datetime):
        dt = value
    else:
        value = str(value)

        if value.endswith("Z"):
            value = value[:-1] + "+00:00"

        dt = datetime.fromisoformat(value)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt


# ============================================================
# SENTINEL-1 COLLECTION
# ============================================================

def _get_collection(
    latitude,
    longitude,
    start_datetime,
    end_datetime,
    radius,
):
    initialize_earth_engine()

    point = ee.Geometry.Point([
        longitude,
        latitude,
    ])

    start = _parse_datetime(start_datetime)
    end = _parse_datetime(end_datetime)

    collection = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(point)
        .filterDate(
            start.isoformat(),
            end.isoformat(),
        )

        # VV is preferred for maritime oil-spill detection.
        .filter(
            ee.Filter.listContains(
                "transmitterReceiverPolarisation",
                "VV",
            )
        )

        # IW is the standard Sentinel-1 mode for most
        # wide-area land/coastal observations.
        .filter(
            ee.Filter.eq(
                "instrumentMode",
                "IW",
            )
        )

        .sort(
            "system:time_start",
            False,
        )
    )

    return collection


# ============================================================
# SEARCH SENTINEL-1
# ============================================================

def search_sentinel1(
    latitude,
    longitude,
    start_datetime,
    end_datetime,
    radius=0.5,
    limit=10,
):
    """
    Search the LIVE Google Earth Engine Sentinel-1 catalogue.

    Returns real acquisitions rather than hardcoded data.
    """

    collection = _get_collection(
        latitude=latitude,
        longitude=longitude,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        radius=radius,
    )

    count = collection.size().getInfo()

    print("\n======================================")
    print("SENTINEL-1 SEARCH")
    print("======================================")
    print("Latitude:", latitude)
    print("Longitude:", longitude)
    print("From:", start_datetime)
    print("To:", end_datetime)
    print("Images found:", count)
    print("======================================\n")

    if count == 0:
        return {
            "type": "FeatureCollection",
            "features": [],
        }

    images = collection.limit(limit)

    image_list = images.toList(limit)

    results = []

    actual_limit = min(count, limit)

    for index in range(actual_limit):

        image = ee.Image(
            image_list.get(index)
        )

        image_id = image.get(
            "system:index"
        ).getInfo()

        timestamp = image.get(
            "system:time_start"
        ).getInfo()

        acquisition = (
            datetime.fromtimestamp(
                timestamp / 1000,
                tz=timezone.utc,
            ).isoformat()
        )

        results.append({
            "id": image_id,
            "acquisition_time": acquisition,

            "orbit_pass": image.get(
                "orbitProperties_pass"
            ).getInfo(),

            "relative_orbit": image.get(
                "relativeOrbitNumber_start"
            ).getInfo(),

            "instrument_mode": image.get(
                "instrumentMode"
            ).getInfo(),

            "polarization": image.get(
                "transmitterReceiverPolarisation"
            ).getInfo(),

            "resolution": image.get(
                "resolution_meters"
            ).getInfo(),
        })

    return {
        "type": "FeatureCollection",
        "features": results,
    }


# ============================================================
# FIND BEST IMAGE
# ============================================================

def get_best_sentinel1_image(
    latitude,
    longitude,
    start_datetime,
    end_datetime,
    search_expansion_hours=48,
):
    """
    Find the most relevant real Sentinel-1 acquisition.

    First searches the requested time window.

    If there is no acquisition, automatically expands the
    search window around the observation period. This is
    necessary because Sentinel-1 does not revisit every
    location every few hours.
    """

    collection = _get_collection(
        latitude,
        longitude,
        start_datetime,
        end_datetime,
        radius=0.5,
    )

    count = collection.size().getInfo()

    # --------------------------------------------------------
    # Expand search if the requested window has no scene
    # --------------------------------------------------------

    if count == 0:

        start = _parse_datetime(start_datetime)
        end = _parse_datetime(end_datetime)

        expanded_start = (
            start.timestamp()
            - search_expansion_hours * 3600
        )

        expanded_end = (
            end.timestamp()
            + search_expansion_hours * 3600
        )

        expanded_start_dt = datetime.fromtimestamp(
            expanded_start,
            tz=timezone.utc,
        )

        expanded_end_dt = datetime.fromtimestamp(
            expanded_end,
            tz=timezone.utc,
        )

        print(
            "No Sentinel-1 image in requested window."
        )

        print(
            "Expanding search to:",
            expanded_start_dt.isoformat(),
            "→",
            expanded_end_dt.isoformat(),
        )

        collection = _get_collection(
            latitude,
            longitude,
            expanded_start_dt.isoformat(),
            expanded_end_dt.isoformat(),
            radius=0.5,
        )

        count = collection.size().getInfo()

    if count == 0:
        return None

    # --------------------------------------------------------
    # Get candidates
    # --------------------------------------------------------

    image_list = collection.toList(
        min(count, 20)
    )

    observation = _parse_datetime(
        end_datetime
    )

    best_image = None
    best_difference = None

    for index in range(
        min(count, 20)
    ):

        image = ee.Image(
            image_list.get(index)
        )

        timestamp = image.get(
            "system:time_start"
        ).getInfo()

        acquisition = datetime.fromtimestamp(
            timestamp / 1000,
            tz=timezone.utc,
        )

        difference = abs(
            (acquisition - observation).total_seconds()
        )

        if (
            best_difference is None
            or difference < best_difference
        ):
            best_difference = difference
            best_image = image

    return best_image


# ============================================================
# DOWNLOAD SCIENTIFIC SENTINEL-1
# ============================================================

def download_sentinel1_scientific(
    latitude,
    longitude,
    start_datetime,
    end_datetime,
    output_path,
    size,
    delta,
):
    """
    Download real Sentinel-1 VV + dataMask from
    Google Earth Engine.

    Output:

        Band 1 = VV backscatter
        Band 2 = data mask
    """

    initialize_earth_engine()

    bbox = build_bbox(
        latitude,
        longitude,
        delta,
    )

    image = get_best_sentinel1_image(
        latitude=latitude,
        longitude=longitude,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
    )

    if image is None:
        raise RuntimeError(
            "No Sentinel-1 VV acquisition was found "
            "for the requested location/time window."
        )

    # --------------------------------------------------------
    # Metadata
    # --------------------------------------------------------

    image_id = image.get(
        "system:index"
    ).getInfo()

    timestamp = image.get(
        "system:time_start"
    ).getInfo()

    acquisition_time = datetime.fromtimestamp(
        timestamp / 1000,
        tz=timezone.utc,
    ).isoformat()

    orbit_pass = image.get(
        "orbitProperties_pass"
    ).getInfo()

    relative_orbit = image.get(
        "relativeOrbitNumber_start"
    ).getInfo()

    instrument_mode = image.get(
        "instrumentMode"
    ).getInfo()

    polarization = image.get(
        "transmitterReceiverPolarisation"
    ).getInfo()

    # --------------------------------------------------------
    # Select actual Sentinel-1 bands
    # --------------------------------------------------------

    scientific_image = image.select([
        "VV",
    ])

    # --------------------------------------------------------
    # Region
    # --------------------------------------------------------

    region = ee.Geometry.Rectangle(
        bbox
    )

    # --------------------------------------------------------
    # Download URL
    # --------------------------------------------------------

    download_params = {
        "name": "slickback_sentinel1",
        "bands": [
            {
                "id": "VV",
                "scale": 10,
                "crs": "EPSG:4326",
            }
        ],
        "region": region,
        "dimensions": f"{size}x{size}",
        "format": "GEO_TIFF",
    }

    print("\n======================================")
    print("SENTINEL-1 EARTH ENGINE DOWNLOAD")
    print("======================================")
    print("Scene:", image_id)
    print("Acquisition:", acquisition_time)
    print("Orbit:", orbit_pass)
    print("Relative orbit:", relative_orbit)
    print("Mode:", instrument_mode)
    print("Polarization:", polarization)
    print("BBox:", bbox)
    print("Size:", size)
    print("======================================\n")

    url = scientific_image.getDownloadURL(
        download_params
    )

    response = requests.get(
        url,
        timeout=180,
    )

    response.raise_for_status()

    output_path = Path(
        output_path
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        output_path,
        "wb",
    ) as file:
        file.write(
            response.content
        )

    return {
        "path": str(output_path),
        "bbox": bbox,

        "width": size,
        "height": size,

        "scene_id": image_id,
        "acquisition_time": acquisition_time,

        "orbit_pass": orbit_pass,
        "relative_orbit": relative_orbit,

        "instrument_mode": instrument_mode,
        "polarization": polarization,
    }


# ============================================================
# VISUALIZATION DOWNLOAD
# ============================================================

def download_sentinel1_image(
    latitude,
    longitude,
    start_datetime,
    end_datetime,
    output_path,
    size,
    delta,
):
    """
    Download a visualization-ready Sentinel-1 VV image.
    """

    initialize_earth_engine()

    bbox = build_bbox(
        latitude,
        longitude,
        delta,
    )

    image = get_best_sentinel1_image(
        latitude,
        longitude,
        start_datetime,
        end_datetime,
    )

    if image is None:
        raise RuntimeError(
            "No Sentinel-1 image found."
        )

    vv = image.select("VV")

    # Convert linear VV backscatter to dB
    vv_db = (
        vv
        .log10()
        .multiply(10)
        .clamp(-30, 5)
    )

    region = ee.Geometry.Rectangle(
        bbox
    )

    params = {
        "name": "slickback_sentinel1_visual",
        "bands": [
            {
                "id": "VV",
                "scale": 10,
                "min": -30,
                "max": 5,
            }
        ],
        "region": region,
        "dimensions": f"{size}x{size}",
        "format": "PNG",
    }

    url = vv_db.getDownloadURL(
        params
    )

    response = requests.get(
        url,
        timeout=180,
    )

    response.raise_for_status()

    output_path = Path(
        output_path
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        output_path,
        "wb",
    ) as file:
        file.write(
            response.content
        )

    return {
        "path": str(output_path),
        "bbox": bbox,
        "width": size,
        "height": size,
    }


# ============================================================
# PIXEL → LAT/LON
# ============================================================

def pixel_to_latlon(
    row,
    col,
    image_height,
    image_width,
    bbox,
):
    if image_height <= 0:
        raise ValueError(
            "image_height must be greater than zero."
        )

    if image_width <= 0:
        raise ValueError(
            "image_width must be greater than zero."
        )

    min_lon, min_lat, max_lon, max_lat = bbox

    longitude = min_lon + (
        (col + 0.5) / image_width
    ) * (
        max_lon - min_lon
    )

    latitude = max_lat - (
        (row + 0.5) / image_height
    ) * (
        max_lat - min_lat
    )

    return {
        "latitude": float(latitude),
        "longitude": float(longitude),
    }