from pathlib import Path
from datetime import datetime, timezone, timedelta

import ee
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

_EE_INITIALIZED = False


# ============================================================
# EARTH ENGINE INITIALIZATION
# ============================================================

def initialize_earth_engine():

    global _EE_INITIALIZED

    if _EE_INITIALIZED:
        return

    if not KEY_FILE.exists():

        raise FileNotFoundError(
            f"Earth Engine service account key not found: {KEY_FILE}"
        )

    credentials = (
        service_account.Credentials
        .from_service_account_file(
            str(KEY_FILE),
            scopes=EE_SCOPE,
        )
    )

    ee.Initialize(
        credentials=credentials,
        project=PROJECT_ID,
    )

    _EE_INITIALIZED = True

    print(
        "Sentinel-2 Earth Engine authentication: OK"
    )


# ============================================================
# DATETIME
# ============================================================

def _parse_datetime(value):

    if isinstance(
        value,
        datetime,
    ):

        dt = value

    else:

        value = str(value)

        if value.endswith("Z"):

            value = (
                value[:-1]
                + "+00:00"
            )

        dt = datetime.fromisoformat(
            value
        )

    if dt.tzinfo is None:

        dt = dt.replace(
            tzinfo=timezone.utc
        )

    return dt


# ============================================================
# CLOUD / SHADOW MASK
# ============================================================

def _mask_clouds(image):
    """
    Mask Sentinel-2 pixels using the SCL band.

    SCL classes removed:

        3  = cloud shadow
        8  = medium probability cloud
        9  = high probability cloud
        10 = cirrus
        11 = snow / ice
    """

    scl = image.select(
        "SCL"
    )

    mask = (
        scl.neq(3)
        .And(
            scl.neq(8)
        )
        .And(
            scl.neq(9)
        )
        .And(
            scl.neq(10)
        )
        .And(
            scl.neq(11)
        )
    )

    return image.updateMask(
        mask
    )


# ============================================================
# FIND SENTINEL-2 SCENE
# ============================================================

def find_sentinel2_scene(
    latitude,
    longitude,
    acquisition_time,
    search_hours=120,
    max_cloud_percentage=100,
):
    """
    Find the closest Sentinel-2 SR scene.

    Searches a broad temporal window around the
    Sentinel-1 acquisition.

    Scene-level cloud percentage is used for ranking,
    while local SCL masking is applied later.
    """

    initialize_earth_engine()

    point = ee.Geometry.Point(
        [
            longitude,
            latitude,
        ]
    )

    acquisition = _parse_datetime(
        acquisition_time
    )

    start = (
        acquisition
        - timedelta(
            hours=search_hours
        )
    )

    end = (
        acquisition
        + timedelta(
            hours=search_hours
        )
    )

    print()
    print(
        "SENTINEL-2 SEARCH"
    )

    print(
        "From:",
        start.isoformat()
    )

    print(
        "To:",
        end.isoformat()
    )

    collection = (
        ee.ImageCollection(
            "COPERNICUS/S2_SR_HARMONIZED"
        )
        .filterBounds(
            point
        )
        .filterDate(
            start.isoformat(),
            end.isoformat(),
        )
        .filter(
            ee.Filter.lte(
                "CLOUDY_PIXEL_PERCENTAGE",
                max_cloud_percentage,
            )
        )
    )

    count = collection.size().getInfo()

    print(
        "Sentinel-2 scenes found:",
        count,
    )

    if count == 0:

        return None

    # --------------------------------------------------------
    # Calculate temporal distance.
    # --------------------------------------------------------

    acquisition_ms = (
        acquisition.timestamp()
        * 1000
    )

    collection = collection.map(
        lambda image:
        image.set(
            "time_difference",
            ee.Number(
                image.get(
                    "system:time_start"
                )
            )
            .subtract(
                acquisition_ms
            )
            .abs(),
        )
    )

    # --------------------------------------------------------
    # Sort by temporal distance.
    # --------------------------------------------------------

    collection = collection.sort(
        "time_difference"
    )

    image = ee.Image(
        collection.first()
    )

    scene_id = image.get(
        "PRODUCT_ID"
    ).getInfo()

    image_id = image.get(
        "system:index"
    ).getInfo()

    scene_time = (
        ee.Date(
            image.get(
                "system:time_start"
            )
        )
        .format()
        .getInfo()
    )

    cloud_percentage = image.get(
        "CLOUDY_PIXEL_PERCENTAGE"
    ).getInfo()

    print(
        "Selected Sentinel-2 scene:",
        scene_id,
    )

    print(
        "Acquisition:",
        scene_time,
    )

    print(
        "Cloud percentage:",
        cloud_percentage,
    )

    return {
        "image": image,

        "scene_id": scene_id,

        "image_id": image_id,

        "acquisition_time": scene_time,

        "cloud_percentage": (
            float(
                cloud_percentage
            )
            if cloud_percentage is not None
            else None
        ),
    }


# ============================================================
# SENTINEL-2 CROSS VALIDATION
# ============================================================

def validate_sentinel2_candidate(
    latitude,
    longitude,
    acquisition_time,
    search_hours=120,
):
    """
    Cross-validate a Sentinel-1 candidate using
    real Sentinel-2 surface-reflectance imagery.

    Sentinel-2 evidence is treated as supporting
    evidence, not proof of oil.
    """

    print()
    print(
        "=" * 60
    )

    print(
        "SENTINEL-2 CROSS VALIDATION"
    )

    print(
        "=" * 60
    )

    print(
        "Candidate:",
        latitude,
        longitude,
    )

    print(
        "Reference time:",
        acquisition_time,
    )

    scene = find_sentinel2_scene(
        latitude=latitude,
        longitude=longitude,
        acquisition_time=acquisition_time,
        search_hours=search_hours,
    )

    if scene is None:

        print(
            "No Sentinel-2 scene available."
        )

        return {
            "available": False,
            "validated": False,
            "confidence": 0.0,
            "reason": (
                "No Sentinel-2 observation "
                "available in the search window."
            ),
        }

    image = scene[
        "image"
    ]

    # --------------------------------------------------------
    # Apply SCL cloud/shadow mask.
    # --------------------------------------------------------

    masked = _mask_clouds(
        image
    )

    point = ee.Geometry.Point(
        [
            longitude,
            latitude,
        ]
    )

    # --------------------------------------------------------
    # Candidate area.
    # --------------------------------------------------------

    candidate_region = point.buffer(
        100
    )

    # --------------------------------------------------------
    # Local reference area.
    # --------------------------------------------------------

    outer_region = point.buffer(
        300
    )

    # --------------------------------------------------------
    # Reflectance bands.
    #
    # Scale factor for Sentinel-2 SR = 10000.
    # --------------------------------------------------------

    blue = (
        masked
        .select("B2")
        .divide(10000)
    )

    green = (
        masked
        .select("B3")
        .divide(10000)
    )

    red = (
        masked
        .select("B4")
        .divide(10000)
    )

    nir = (
        masked
        .select("B8")
        .divide(10000)
    )

    # --------------------------------------------------------
    # NDVI
    # --------------------------------------------------------

    ndvi = (
        nir.subtract(red)
        .divide(
            nir.add(red).max(
                0.0001
            )
        )
        .rename(
            "NDVI"
        )
    )

    # --------------------------------------------------------
    # NDWI
    # --------------------------------------------------------

    ndwi = (
        green.subtract(nir)
        .divide(
            green.add(nir).max(
                0.0001
            )
        )
        .rename(
            "NDWI"
        )
    )

    # --------------------------------------------------------
    # Stack
    # --------------------------------------------------------

    optical = (
        blue
        .rename("BLUE")
        .addBands(
            green.rename("GREEN")
        )
        .addBands(
            red.rename("RED")
        )
        .addBands(
            nir.rename("NIR")
        )
        .addBands(
            ndvi
        )
        .addBands(
            ndwi
        )
    )

    # --------------------------------------------------------
    # Candidate statistics.
    # --------------------------------------------------------

    candidate_stats = (
        optical
        .reduceRegion(
            reducer=ee.Reducer.median(),
            geometry=candidate_region,
            scale=10,
            bestEffort=True,
            maxPixels=100000,
        )
        .getInfo()
    )

    # --------------------------------------------------------
    # Local reference statistics.
    # --------------------------------------------------------

    outer_stats = (
        optical
        .reduceRegion(
            reducer=ee.Reducer.median(),
            geometry=outer_region,
            scale=10,
            bestEffort=True,
            maxPixels=100000,
        )
        .getInfo()
    )

    # --------------------------------------------------------
    # No usable optical pixels.
    # --------------------------------------------------------

    if not candidate_stats:

        return {
            "available": True,
            "validated": False,
            "confidence": 0.0,
            "reason": (
                "Sentinel-2 scene exists, but the "
                "candidate area is masked or has "
                "no usable optical pixels."
            ),
            "scene": {
                "scene_id": scene[
                    "scene_id"
                ],
                "acquisition_time": scene[
                    "acquisition_time"
                ],
                "cloud_percentage": scene[
                    "cloud_percentage"
                ],
            },
        }

    # ========================================================
    # VALUE HELPER
    # ========================================================

    def get_value(
        dictionary,
        key,
    ):

        value = dictionary.get(
            key
        )

        if value is None:

            return None

        return float(
            value
        )

    candidate_ndvi = get_value(
        candidate_stats,
        "NDVI",
    )

    candidate_ndwi = get_value(
        candidate_stats,
        "NDWI",
    )

    candidate_red = get_value(
        candidate_stats,
        "RED",
    )

    candidate_nir = get_value(
        candidate_stats,
        "NIR",
    )

    outer_ndvi = get_value(
        outer_stats,
        "NDVI",
    )

    outer_ndwi = get_value(
        outer_stats,
        "NDWI",
    )

    outer_red = get_value(
        outer_stats,
        "RED",
    )

    outer_nir = get_value(
        outer_stats,
        "NIR",
    )

    # ========================================================
    # LOCAL DIFFERENCES
    # ========================================================

    ndvi_difference = None

    if (
        candidate_ndvi is not None
        and outer_ndvi is not None
    ):

        ndvi_difference = (
            candidate_ndvi
            - outer_ndvi
        )

    ndwi_difference = None

    if (
        candidate_ndwi is not None
        and outer_ndwi is not None
    ):

        ndwi_difference = (
            candidate_ndwi
            - outer_ndwi
        )

    red_difference = None

    if (
        candidate_red is not None
        and outer_red is not None
    ):

        red_difference = (
            candidate_red
            - outer_red
        )

    nir_difference = None

    if (
        candidate_nir is not None
        and outer_nir is not None
    ):

        nir_difference = (
            candidate_nir
            - outer_nir
        )

    # ========================================================
    # EVIDENCE SCORING
    # ========================================================

    score = 0.0

    indicators = []

    # --------------------------------------------------------
    # NDWI
    # --------------------------------------------------------

    if (
        ndwi_difference is not None
        and ndwi_difference < -0.03
    ):

        score += 0.25

        indicators.append(
            "LOCAL NDWI ANOMALY"
        )

    # --------------------------------------------------------
    # NDVI
    # --------------------------------------------------------

    if (
        ndvi_difference is not None
        and ndvi_difference < -0.03
    ):

        score += 0.20

        indicators.append(
            "LOCAL NDVI ANOMALY"
        )

    # --------------------------------------------------------
    # Red band
    # --------------------------------------------------------

    if (
        red_difference is not None
        and abs(red_difference) > 0.005
    ):

        score += 0.20

        indicators.append(
            "LOCAL RED-BAND ANOMALY"
        )

    # --------------------------------------------------------
    # NIR band
    # --------------------------------------------------------

    if (
        nir_difference is not None
        and abs(nir_difference) > 0.005
    ):

        score += 0.20

        indicators.append(
            "LOCAL NIR-BAND ANOMALY"
        )

    # --------------------------------------------------------
    # Cloud penalty.
    # --------------------------------------------------------

    cloud_percentage = (
        scene[
            "cloud_percentage"
        ]
    )

    cloud_penalty = 0.0

    if cloud_percentage is not None:

        if cloud_percentage > 80:

            cloud_penalty = 0.20

        elif cloud_percentage > 60:

            cloud_penalty = 0.10

        elif cloud_percentage > 40:

            cloud_penalty = 0.05

    score = max(
        0.0,
        min(
            1.0,
            score - cloud_penalty,
        ),
    )

    validated = (
        score >= 0.35
        and cloud_percentage is not None
        and cloud_percentage < 80
    )

    # ========================================================
    # RESULT
    # ========================================================

    result = {

        "available": True,

        "validated": bool(
            validated
        ),

        "confidence": round(
            score,
            3,
        ),

        "indicators": indicators,

        "scene": {

            "scene_id": scene[
                "scene_id"
            ],

            "image_id": scene[
                "image_id"
            ],

            "acquisition_time": scene[
                "acquisition_time"
            ],

            "cloud_percentage": cloud_percentage,
        },

        "candidate": {

            "ndvi": candidate_ndvi,

            "ndwi": candidate_ndwi,

            "red_reflectance": candidate_red,

            "nir_reflectance": candidate_nir,
        },

        "local_reference": {

            "ndvi": outer_ndvi,

            "ndwi": outer_ndwi,

            "red_reflectance": outer_red,

            "nir_reflectance": outer_nir,
        },

        "differences": {

            "ndvi": ndvi_difference,

            "ndwi": ndwi_difference,

            "red_reflectance": red_difference,

            "nir_reflectance": nir_difference,
        },

        "interpretation": (
            "Sentinel-2 provides supporting optical "
            "evidence spatially associated with the "
            "Sentinel-1 anomaly."
            if validated
            else
            "Sentinel-2 does not provide strong "
            "optical confirmation of the "
            "Sentinel-1 anomaly."
        ),
    }

    print()
    print(
        "Sentinel-2 scene:",
        scene[
            "scene_id"
        ],
    )

    print(
        "Cloud percentage:",
        cloud_percentage,
    )

    print(
        "Optical confidence:",
        result[
            "confidence"
        ],
    )

    print(
        "Validated:",
        result[
            "validated"
        ],
    )

    print(
        "Indicators:",
        indicators,
    )

    return result