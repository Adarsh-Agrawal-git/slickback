import requests

from .auth import get_access_token


CATALOG_URL = "https://sh.dataspace.copernicus.eu/catalog/v1/search"
PROCESS_URL = "https://sh.dataspace.copernicus.eu/process/v1"


def build_bbox(latitude, longitude, delta):
    """
    Build a geographic bounding box around the requested AOI.

    Returns:
        [min_longitude, min_latitude,
         max_longitude, max_latitude]
    """

    if delta <= 0:
        raise ValueError("delta must be greater than zero.")

    return [
        longitude - delta,
        latitude - delta,
        longitude + delta,
        latitude + delta,
    ]


def search_sentinel1(
    latitude,
    longitude,
    start_datetime,
    end_datetime,
    radius=0.5,
    limit=10,
):
    """
    Search the real Copernicus Data Space catalogue
    for Sentinel-1 GRD acquisitions.
    """

    bbox = build_bbox(
        latitude,
        longitude,
        radius,
    )

    payload = {
        "bbox": bbox,
        "datetime": f"{start_datetime}/{end_datetime}",
        "collections": ["sentinel-1-grd"],
        "limit": limit,
        "fields": {
            "include": [
                "id",
                "geometry",
                "bbox",
                "properties.datetime",
                "properties.sar:instrument_mode",
                "properties.sat:orbit_state",
                "properties.s1:polarization",
                "properties.s1:resolution",
            ]
        },
    }

    token = get_access_token()

    response = requests.post(
        CATALOG_URL,
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        timeout=60,
    )

    response.raise_for_status()

    return response.json()


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
    Download a visualization-ready Sentinel-1 GRD image.

    Used for visualization/debugging.
    """

    bbox = build_bbox(
        latitude,
        longitude,
        delta,
    )

    evalscript = """
    //VERSION=3

    function setup() {
        return {
            input: ["VV"],
            output: {
                id: "default",
                bands: 1,
                sampleType: SampleType.AUTO
            }
        };
    }

    function evaluatePixel(samples) {
        return [samples.VV];
    }
    """

    payload = {
        "input": {
            "bounds": {
                "bbox": bbox,
                "properties": {
                    "crs": "http://www.opengis.net/def/crs/EPSG/0/4326"
                }
            },
            "data": [
                {
                    "type": "sentinel-1-grd",
                    "dataFilter": {
                        "timeRange": {
                            "from": start_datetime,
                            "to": end_datetime,
                        }
                    },
                    "processing": {
                        "orthorectify": "true"
                    }
                }
            ]
        },

        "output": {
            "width": size,
            "height": size,
            "responses": [
                {
                    "identifier": "default",
                    "format": {
                        "type": "image/png"
                    }
                }
            ]
        },

        "evalscript": evalscript
    }

    token = get_access_token()

    response = requests.post(
        PROCESS_URL,
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "image/png",
        },
        timeout=180,
    )

    if not response.ok:
        print("\nCOPERNICUS PROCESS API ERROR")
        print("Status:", response.status_code)
        print(response.text)
        print()

    response.raise_for_status()

    with open(output_path, "wb") as file:
        file.write(response.content)

    return {
        "path": output_path,
        "bbox": bbox,
        "width": size,
        "height": size,
    }


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
    Download real Sentinel-1 VV backscatter.

    Band 0 = VV backscatter
    Band 1 = data mask

    VV is returned as floating-point linear backscatter
    and converted to dB later in preprocess.py.
    """

    bbox = build_bbox(
        latitude,
        longitude,
        delta,
    )

    evalscript = """
    //VERSION=3

    function setup() {
        return {
            input: ["VV", "dataMask"],
            output: {
                id: "default",
                bands: 2,
                sampleType: SampleType.FLOAT32
            }
        };
    }

    function evaluatePixel(sample) {
        return [
            sample.VV,
            sample.dataMask
        ];
    }
    """

    payload = {
        "input": {
            "bounds": {
                "bbox": bbox,
                "properties": {
                    "crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
                }
            },

            "data": [
                {
                    "type": "sentinel-1-grd",

                    "dataFilter": {
                        "timeRange": {
                            "from": start_datetime,
                            "to": end_datetime
                        },
                        "mosaickingOrder": "mostRecent"
                    },

                    "processing": {
                        "orthorectify": "true",
                        "backCoeff": "GAMMA0_ELLIPSOID"
                    }
                }
            ]
        },

        "output": {
            "width": size,
            "height": size,

            "responses": [
                {
                    "identifier": "default",
                    "format": {
                        "type": "image/tiff"
                    }
                }
            ]
        },

        "evalscript": evalscript
    }

    token = get_access_token()

    print("\n======================================")
    print("SENTINEL-1 DOWNLOAD")
    print("======================================")
    print("BBox:", bbox)
    print("From:", start_datetime)
    print("To:", end_datetime)
    print("Image size:", size)
    print("======================================\n")

    response = requests.post(
        PROCESS_URL,
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "image/tiff",
        },
        timeout=180,
    )

    if not response.ok:
        print("\n======================================")
        print("COPERNICUS PROCESS API ERROR")
        print("======================================")
        print("Status:", response.status_code)
        print(response.text)
        print("======================================\n")

    response.raise_for_status()

    with open(output_path, "wb") as file:
        file.write(response.content)

    return {
        "path": output_path,
        "bbox": bbox,
        "width": size,
        "height": size,
    }

def pixel_to_latlon(
    row,
    col,
    image_height,
    image_width,
    bbox,
):
    """
    Convert image pixel coordinates into
    geographic latitude/longitude.

    bbox:
        [min_longitude, min_latitude,
         max_longitude, max_latitude]
    """

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
    ) * (max_lon - min_lon)

    latitude = max_lat - (
        (row + 0.5) / image_height
    ) * (max_lat - min_lat)

    return {
        "latitude": float(latitude),
        "longitude": float(longitude),
    }