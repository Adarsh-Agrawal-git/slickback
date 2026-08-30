"""
Sentinel-2 optical cross-validation for SlickBack.

Purpose:
    Use Sentinel-2 optical imagery as supporting evidence for
    Sentinel-1 SAR dark-region candidates.

Important:
    Sentinel-2 does NOT independently prove that a candidate is oil.
    It provides optical support, weak support, or no usable evidence.

Pipeline:

    Sentinel-1 candidate
          ↓
    Sentinel-2 scene search
          ↓
    Cloud filtering
          ↓
    SCL cloud/shadow masking
          ↓
    Spectral indices
          ↓
    Local spectral comparison
          ↓
    Optical validation result
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path
import math
import os

import ee
import numpy as np

from satellite.sentinel1 import initialize_earth_engine

# ============================================================
# CONSTANTS
# ============================================================

DEFAULT_SEARCH_HOURS = 120
DEFAULT_MAX_CLOUD_PERCENTAGE = 60.0

# Sentinel-2 bands used by the validation.
BAND_BLUE = "B2"
BAND_GREEN = "B3"
BAND_RED = "B4"
BAND_NIR = "B8"
BAND_SWIR1 = "B11"
BAND_SWIR2 = "B12"
BAND_SCL = "SCL"


# ============================================================
# EARTH ENGINE INITIALIZATION
# ============================================================

def _initialize_earth_engine():
    """
    Reuse the authenticated Earth Engine initialization
    from sentinel1.py.
    """

    initialize_earth_engine()

    print(
        "Sentinel-2 Earth Engine session: OK"
    )
#=========================================================
# DATETIME HELPERS
# ============================================================

def _ensure_utc(value):
    """
    Convert datetime/string input into timezone-aware UTC datetime.
    """

    if isinstance(value, datetime):

        result = value

    elif isinstance(value, str):

        text = value.strip()

        if text.endswith("Z"):
            text = text[:-1] + "+00:00"

        result = datetime.fromisoformat(
            text
        )

    else:

        raise TypeError(
            "acquisition_time must be a datetime "
            "or ISO datetime string."
        )

    if result.tzinfo is None:

        result = result.replace(
            tzinfo=timezone.utc
        )

    return result.astimezone(
        timezone.utc
    )


# ============================================================
# GEOMETRY
# ============================================================

def _candidate_geometry(
    latitude,
    longitude,
    delta=0.025,
):
    """
    Create a small geometry around a candidate.
    """

    latitude = float(latitude)
    longitude = float(longitude)
    delta = float(delta)

    return ee.Geometry.Rectangle(
        [
            longitude - delta,
            latitude - delta,
            longitude + delta,
            latitude + delta,
        ]
    )


# ============================================================
# SENTINEL-2 SCENE SEARCH
# ============================================================

def find_sentinel2_scene(
    latitude,
    longitude,
    acquisition_time,
    search_hours=DEFAULT_SEARCH_HOURS,
    max_cloud_percentage=DEFAULT_MAX_CLOUD_PERCENTAGE,
):
    """
    Find the best Sentinel-2 scene near the candidate.

    Scene ranking considers:

        1. cloud percentage
        2. temporal distance

    A highly cloudy scene is not allowed to dominate simply
    because it is temporally closer.
    """

    _initialize_earth_engine()

    acquisition_time = _ensure_utc(
        acquisition_time
    )

    search_hours = float(
        search_hours
    )

    start_time = (
        acquisition_time
        - timedelta(
            hours=search_hours
        )
    )

    end_time = (
        acquisition_time
        + timedelta(
            hours=search_hours
        )
    )

    geometry = _candidate_geometry(
        latitude,
        longitude,
        delta=0.05,
    )

    start_millis = int(
        start_time.timestamp() * 1000
    )

    target_millis = int(
        acquisition_time.timestamp() * 1000
    )

    collection = (
        ee.ImageCollection(
            "COPERNICUS/S2_SR_HARMONIZED"
        )
        .filterBounds(
            geometry
        )
        .filterDate(
            start_time.isoformat(),
            end_time.isoformat(),
        )
    )

    # --------------------------------------------------------
    # Attach temporal distance.
    # --------------------------------------------------------

    def add_time_difference(image):

        image_time = ee.Number(
            image.get(
                "system:time_start"
            )
        )

        difference = (
            image_time
            .subtract(
                target_millis
            )
            .abs()
        )

        return image.set(
            "time_difference",
            difference,
        )

    collection = collection.map(
        add_time_difference
    )

    count = collection.size().getInfo()

    print()
    print(
        "SENTINEL-2 SCENE SEARCH"
    )

    print(
        "Search window:",
        start_time.isoformat(),
        "→",
        end_time.isoformat(),
    )

    print(
        "Maximum cloud percentage:",
        max_cloud_percentage,
    )

    print(
        "Sentinel-2 scenes found:",
        count,
    )

    if count == 0:

        return None

    # --------------------------------------------------------
    # Rank scenes using cloud + temporal distance.
    #
    # Cloud is deliberately weighted strongly.
    # Temporal distance breaks ties between similarly clear
    # scenes.
    # --------------------------------------------------------

    def add_scene_score(image):

        cloud = ee.Number(
            image.get(
                "CLOUDY_PIXEL_PERCENTAGE"
            )
        )

        image_time = ee.Number(
            image.get(
                "system:time_start"
            )
        )

        time_difference_hours = (
            image_time
            .subtract(
                target_millis
            )
            .abs()
            .divide(
                1000 * 60 * 60
            )
        )

        scene_score = (
            cloud.multiply(10)
            .add(
                time_difference_hours
            )
        )

        return image.set(
            "time_difference",
            time_difference_hours
        ).set(
            "scene_score",
            scene_score
        )

    collection = collection.map(
        add_scene_score
    )  

    # --------------------------------------------------------
    # Prefer scenes with usable scene-level cloud cover.
    #
    # Scenes <= 60% cloud are preferred.
    # If none exist, retain the least-cloudy available scenes
    # rather than failing S2 completely.
    # --------------------------------------------------------

    usable_collection = collection.filter(
        ee.Filter.lte(
            "CLOUDY_PIXEL_PERCENTAGE",
            60,
        )
    )

    usable_count = usable_collection.size().getInfo()

    if usable_count > 0:

        print(
            "Sentinel-2 usable scenes (cloud <= 60%):",
            usable_count,
        )

        collection = usable_collection

    else:

        print(
            "WARNING: No Sentinel-2 scene has cloud <= 60%."
        )

        print(
            "Using the least-cloudy available scene "
            "for candidate-level SCL validation."
        )

    # --------------------------------------------------------
    # Re-score after filtering.
    # --------------------------------------------------------

    collection = collection.sort(
        "scene_score"
    )

    image = ee.Image(
        collection.first()
    )

    # --------------------------------------------------------
    # Metadata.
    # --------------------------------------------------------

    scene_id = image.get(
        "PRODUCT_ID"
    ).getInfo()

    if not scene_id:

        scene_id = image.get(
            "system:index"
        ).getInfo()

    acquisition_millis = image.get(
        "system:time_start"
    ).getInfo()

    acquisition_datetime = (
        datetime.fromtimestamp(
            acquisition_millis / 1000,
            tz=timezone.utc,
        )
    )

    cloud_percentage = image.get(
        "CLOUDY_PIXEL_PERCENTAGE"
    ).getInfo()

    scene_score = image.get(
        "scene_score"
    ).getInfo()

    time_difference_hours = (
        abs(
            acquisition_millis
            - target_millis
        )
        / 1000
        / 60
        / 60
    )

    print()
    print(
        "SELECTED SENTINEL-2 SCENE"
    )

    print(
        "Scene:",
        scene_id,
    )

    print(
        "Acquisition:",
        acquisition_datetime.isoformat(),
    )

    print(
        "Cloud percentage:",
        round(
            float(
                cloud_percentage
            ),
            3,
        ),
    )

    print(
        "Temporal difference:",
        round(
            time_difference_hours,
            3,
        ),
        "hours",
    )

    print(
        "Scene score:",
        round(
            float(
                scene_score
            ),
            3,
        ),
    )

    return {
        "image": image,
        "scene_id": scene_id,
        "acquisition_time": (
            acquisition_datetime
        ),
        "cloud_percentage": float(
            cloud_percentage
        ),
        "temporal_difference_hours": float(
            time_difference_hours
        ),
        "scene_score": float(
            scene_score
        ),
        "search_start": start_time,
        "search_end": end_time,
    }


# ============================================================
# SCL CLOUD / SHADOW MASK
# ============================================================

def apply_scl_mask(image):
    """
    Mask Sentinel-2 pixels using the Scene Classification Layer.

    Masked classes include:

        0  No data
        1  Saturated / defective
        3  Cloud shadow
        8  Medium probability cloud
        9  High probability cloud
        10 Thin cirrus
        11 Snow / ice
    """

    scl = image.select(
        BAND_SCL
    )

    valid = (
        scl.neq(0)
        .And(
            scl.neq(1)
        )
        .And(
            scl.neq(3)
        )
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
        valid
    )


# ============================================================
# SPECTRAL INDICES
# ============================================================

def add_spectral_indices(image):
    """
    Add optical indices used for candidate validation.

    NDVI:
        vegetation indicator

    NDWI:
        water-related indicator

    MNDWI:
        water / surface discrimination

    NDSI:
        snow / ice indicator
    """

    ndvi = image.normalizedDifference(
        [
            BAND_NIR,
            BAND_RED,
        ]
    ).rename(
        "NDVI"
    )

    ndwi = image.normalizedDifference(
        [
            BAND_GREEN,
            BAND_NIR,
        ]
    ).rename(
        "NDWI"
    )

    mndwi = image.normalizedDifference(
        [
            BAND_GREEN,
            BAND_SWIR1,
        ]
    ).rename(
        "MNDWI"
    )

    ndsi = image.normalizedDifference(
        [
            BAND_GREEN,
            BAND_SWIR1,
        ]
    ).rename(
        "NDSI"
    )

    return image.addBands(
        [
            ndvi,
            ndwi,
            mndwi,
            ndsi,
        ]
    )


# ============================================================
# LOCAL STATISTICS
# ============================================================

def _get_region_statistics(
    image,
    geometry,
    scale=20,
):
    """
    Extract local spectral statistics.
    """

    bands = [
        BAND_BLUE,
        BAND_GREEN,
        BAND_RED,
        BAND_NIR,
        BAND_SWIR1,
        BAND_SWIR2,
        "NDVI",
        "NDWI",
        "MNDWI",
        "NDSI",
    ]

    reducer = (
        ee.Reducer.mean()
        .combine(
            reducer2=ee.Reducer.stdDev(),
            sharedInputs=True,
        )
        .combine(
            reducer2=ee.Reducer.minMax(),
            sharedInputs=True,
        )
    )

    result = image.select(
        bands
    ).reduceRegion(
        reducer=reducer,
        geometry=geometry,
        scale=scale,
        bestEffort=True,
        maxPixels=100000,
    )

    return result.getInfo()


def _safe_float(
    value,
    default=None,
):
    """
    Convert a value safely to float.
    """

    if value is None:
        return default

    try:

        value = float(value)

        if not math.isfinite(
            value
        ):
            return default

        return value

    except (
        TypeError,
        ValueError,
    ):

        return default


# ============================================================
# OPTICAL CANDIDATE ANALYSIS
# ============================================================

def analyze_optical_candidate(
    image,
    latitude,
    longitude,
    candidate_delta=0.01,
):
    """
    Analyse the optical region around a SAR candidate.

    The analysis is intentionally conservative.

    Sentinel-2 evidence is treated as supporting evidence,
    not as proof of an oil spill.
    """

    candidate_geometry = _candidate_geometry(
        latitude,
        longitude,
        delta=candidate_delta,
    )

    # --------------------------------------------------------
    # Mask and indices.
    # --------------------------------------------------------

    masked = apply_scl_mask(
        image
    )

    processed = add_spectral_indices(
        masked
    )

    statistics = _get_region_statistics(
        processed,
        candidate_geometry,
        scale=20,
    )

    if not statistics:

        return {
            "valid": False,
            "confidence": 0.0,
            "reason": (
                "No valid Sentinel-2 pixels "
                "were available for the candidate."
            ),
        }

    # --------------------------------------------------------
    # Extract means.
    # --------------------------------------------------------

    blue = _safe_float(
        statistics.get(
            "B2_mean"
        )
    )

    green = _safe_float(
        statistics.get(
            "B3_mean"
        )
    )

    red = _safe_float(
        statistics.get(
            "B4_mean"
        )
    )

    nir = _safe_float(
        statistics.get(
            "B8_mean"
        )
    )

    swir1 = _safe_float(
        statistics.get(
            "B11_mean"
        )
    )

    swir2 = _safe_float(
        statistics.get(
            "B12_mean"
        )
    )

    ndvi = _safe_float(
        statistics.get(
            "NDVI_mean"
        )
    )

    ndwi = _safe_float(
        statistics.get(
            "NDWI_mean"
        )
    )

    mndwi = _safe_float(
        statistics.get(
            "MNDWI_mean"
        )
    )

    ndsi = _safe_float(
        statistics.get(
            "NDSI_mean"
        )
    )

    # --------------------------------------------------------
    # Validity check.
    # --------------------------------------------------------

    required_values = [
        blue,
        green,
        red,
        nir,
        swir1,
        swir2,
    ]

    if any(
        value is None
        for value in required_values
    ):

        return {
            "valid": False,
            "confidence": 0.0,
            "reason": (
                "Insufficient valid optical "
                "pixels after cloud masking."
            ),
            "statistics": statistics,
        }

    # --------------------------------------------------------
    # Conservative optical indicators.
    #
    # These are NOT an oil classifier.
    # They only detect unusual low-reflectance /
    # water-surface spectral behavior.
    # --------------------------------------------------------

    indicators = []

    score = 0.0

    # Low NIR reflectance relative to surrounding water
    # can support a surface anomaly, but is not specific
    # to oil.
    nir_scaled = nir / 10000.0

    if nir_scaled < 0.08:

        score += 15.0

        indicators.append(
            "low near-infrared reflectance"
        )

    # Low SWIR response can be consistent with a water-like
    # surface and helps reject bright land/vegetation.
    swir_scaled = swir1 / 10000.0

    if swir_scaled < 0.10:

        score += 10.0

        indicators.append(
            "low SWIR reflectance"
        )

    # Vegetation should not dominate a sea-surface candidate.
    if ndvi is not None and ndvi < 0.20:

        score += 10.0

        indicators.append(
            "low vegetation signal"
        )

    # Water-like spectral response.
    if mndwi is not None and mndwi > 0:

        score += 10.0

        indicators.append(
            "water-like spectral response"
        )

    # Penalize strong vegetation.
    if ndvi is not None and ndvi > 0.45:

        score -= 25.0

        indicators.append(
            "strong vegetation signal"
        )

    # Penalize snow/ice.
    if ndsi is not None and ndsi > 0.4:

        score -= 30.0

        indicators.append(
            "snow/ice-like spectral response"
        )

    # Clamp.
    score = max(
        0.0,
        min(
            score,
            100.0,
        ),
    )

    if score >= 50:

        validation = "SUPPORTED"

    elif score >= 25:

        validation = "WEAK_SUPPORT"

    else:

        validation = "NOT_SUPPORTED"

    return {
        "valid": True,
        "validated": (
            validation == "SUPPORTED"
        ),
        "validation": validation,
        "confidence": round(
            score,
            2,
        ),
        "indicators": indicators,
        "statistics": {
            "blue_mean": blue,
            "green_mean": green,
            "red_mean": red,
            "nir_mean": nir,
            "swir1_mean": swir1,
            "swir2_mean": swir2,
            "ndvi_mean": ndvi,
            "ndwi_mean": ndwi,
            "mndwi_mean": mndwi,
            "ndsi_mean": ndsi,
        },
    }


# ============================================================
# CANDIDATE VALIDATION
# ============================================================

def validate_sentinel2_candidate(
    latitude,
    longitude,
    acquisition_time,
    search_hours=DEFAULT_SEARCH_HOURS,
):
    """
    Complete Sentinel-2 validation for one SAR candidate.

    Returns a stable result even when Sentinel-2 cannot provide
    useful evidence.
    """

    print()
    print(
        "------------------------------------------------------------"
    )

    print(
        "SENTINEL-2 CANDIDATE VALIDATION"
    )

    print(
        "Candidate:",
        float(latitude),
        float(longitude),
    )

    print(
        "------------------------------------------------------------"
    )

    try:

        scene = find_sentinel2_scene(
            latitude=latitude,
            longitude=longitude,
            acquisition_time=acquisition_time,
            search_hours=search_hours,
            max_cloud_percentage=60,
        )

    except Exception as error:

        print(
            "Sentinel-2 scene search failed:",
            repr(error),
        )

        return {
            "available": False,
            "validated": False,
            "validation": "UNAVAILABLE",
            "confidence": 0.0,
            "reason": str(error),
        }

    if scene is None:

        print(
            "No usable Sentinel-2 scene found."
        )

        return {
            "available": False,
            "validated": False,
            "validation": "NO_SCENE",
            "confidence": 0.0,
            "reason": (
                "No Sentinel-2 scene satisfied "
                "the cloud and temporal search criteria."
            ),
        }

    cloud_percentage = (
        scene["cloud_percentage"]
    )

        # --------------------------------------------------------
    # Candidate-level cloud validation
    # --------------------------------------------------------
    #
    # Do not reject a scene using whole-scene cloud percentage.
    # A scene may be cloudy elsewhere while the SAR candidate
    # itself is clear.
    #
    # The SCL mask inside analyze_optical_candidate() performs
    # the actual pixel-level cloud/shadow filtering.
    # --------------------------------------------------------

    if cloud_percentage > 60:

        print(
            "Sentinel-2 scene has high scene-level cloud cover:",
            cloud_percentage,
        )

        print(
            "Proceeding with candidate-level SCL cloud assessment..."
        )

    try:

        optical = analyze_optical_candidate(
            image=scene["image"],
            latitude=latitude,
            longitude=longitude,
        )

    except Exception as error:

        print(
            "Sentinel-2 optical analysis failed:",
            repr(error),
        )

        return {
            "available": True,
            "validated": False,
            "validation": "ANALYSIS_FAILED",
            "confidence": 0.0,
            "cloud_percentage": cloud_percentage,
            "scene_id": scene["scene_id"],
            "acquisition_time": (
                scene[
                    "acquisition_time"
                ].isoformat()
            ),
            "reason": str(error),
        }

    result = {
        "available": True,
        "validated": bool(
            optical.get(
                "validated",
                False,
            )
        ),
        "validation": optical.get(
            "validation",
            "NOT_SUPPORTED",
        ),
        "confidence": float(
            optical.get(
                "confidence",
                0.0,
            )
        ),
        "cloud_percentage": float(
            cloud_percentage
        ),
        "scene_id": scene[
            "scene_id"
        ],
        "acquisition_time": (
            scene[
                "acquisition_time"
            ].isoformat()
        ),
        "temporal_difference_hours": float(
            scene[
                "temporal_difference_hours"
            ]
        ),
        "indicators": optical.get(
            "indicators",
            [],
        ),
        "statistics": optical.get(
            "statistics",
            {},
        ),
    }

    print()
    print(
        "SENTINEL-2 VALIDATION RESULT"
    )

    print(
        "Scene:",
        result["scene_id"],
    )

    print(
        "Cloud:",
        round(
            result["cloud_percentage"],
            2,
        ),
        "%",
    )

    print(
        "Optical validation:",
        result["validation"],
    )

    print(
        "Optical confidence:",
        result["confidence"],
    )

    if result["indicators"]:

        print(
            "Indicators:"
        )

        for indicator in result[
            "indicators"
        ]:

            print(
                "  -",
                indicator,
            )

    return result


# ============================================================
# BACKWARD-COMPATIBILITY ALIAS
# ============================================================

validate_candidate = (
    validate_sentinel2_candidate
)


# ============================================================
# MODULE TEST
# ============================================================

if __name__ == "__main__":

    print(
        "Sentinel-2 validation module loaded."
    )

    print(
        "Use validate_sentinel2_candidate() "
        "from the SlickBack pipeline."
    )