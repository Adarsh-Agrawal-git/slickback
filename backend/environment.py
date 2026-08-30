import math
from datetime import datetime, timezone
import json
import requests


WEATHER_URL = (
    "https://archive-api.open-meteo.com/v1/archive"
)

MARINE_URL = (
    "https://marine-api.open-meteo.com/v1/marine"
)


def _parse_datetime(value):
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value)

        if text.endswith("Z"):
            text = text[:-1] + "+00:00"

        dt = datetime.fromisoformat(text)

    if dt.tzinfo is None:
        dt = dt.replace(
            tzinfo=timezone.utc
        )

    return dt


def _get_json(url, params):
    """
    Fetch JSON from an HTTPS API using requests.

    Uses the certifi CA bundle instead of Python urllib's
    system SSL handling.
    """

    import certifi

    try:
        response = requests.get(
            url,
            params=params,
            timeout=30,
            verify=certifi.where(),
        )

        response.raise_for_status()

        return response.json()

    except requests.exceptions.SSLError as error:
        raise RuntimeError(
            f"SSL certificate verification failed while "
            f"connecting to {url}: {error}"
        ) from error

    except requests.exceptions.Timeout as error:
        raise RuntimeError(
            f"Environmental API request timed out: {url}"
        ) from error

    except requests.exceptions.RequestException as error:
        raise RuntimeError(
            f"Environmental API request failed: {error}"
        ) from error

    except ValueError as error:
        raise RuntimeError(
            f"Environmental API returned invalid JSON: {error}"
        ) from error

def _nearest_hour_index(
    times,
    target
):
    if not times:
        raise ValueError(
            "Environmental API returned no timestamps."
        )

    target = _parse_datetime(
        target
    )

    best_index = None
    best_difference = None

    for index, timestamp in enumerate(times):

        dt = _parse_datetime(
            timestamp
        )

        difference = abs(
            (
                dt - target
            ).total_seconds()
        )

        if (
            best_difference is None
            or difference < best_difference
        ):
            best_difference = difference
            best_index = index

    return best_index


def fetch_wind(
    latitude,
    longitude,
    observation_time
):
    """
    Retrieve historical 10 m wind data.

    Source:
        Open-Meteo Historical Weather API.

    Returns:
        speed in km/h
        direction in degrees
    """

    dt = _parse_datetime(
        observation_time
    )

    date = dt.date().isoformat()

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": date,
        "end_date": date,
        "hourly": (
            "wind_speed_10m,"
            "wind_direction_10m"
        ),
        "wind_speed_unit": "kmh",
        "timezone": "UTC",
        "cell_selection": "sea",
    }

    data = _get_json(
        WEATHER_URL,
        params
    )

    hourly = data.get(
        "hourly",
        {}
    )

    times = hourly.get(
        "time",
        []
    )

    speeds = hourly.get(
        "wind_speed_10m",
        []
    )

    directions = hourly.get(
        "wind_direction_10m",
        []
    )

    index = _nearest_hour_index(
        times,
        dt
    )

    speed = speeds[index]
    direction = directions[index]

    if speed is None or direction is None:
        raise ValueError(
            "Historical wind data is unavailable "
            "for the requested time."
        )

    return {
        "speed_kmh": float(
            speed
        ),
        "direction_deg": float(
            direction
        ),
        "timestamp": times[index],
        "provider": (
            "Open-Meteo Historical Weather"
        ),
    }


def fetch_current(
    latitude,
    longitude,
    observation_time
):
    """
    Retrieve modeled ocean current data.

    Source:
        Open-Meteo Marine API.

    Returns:
        current velocity in km/h
        current direction in degrees

    Direction convention:
        direction toward which the current flows.
    """

    dt = _parse_datetime(
        observation_time
    )

    date = dt.date().isoformat()

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": date,
        "end_date": date,
        "hourly": (
            "ocean_current_velocity,"
            "ocean_current_direction"
        ),
        "timezone": "UTC",
        "cell_selection": "sea",
    }

    data = _get_json(
        MARINE_URL,
        params
    )

    hourly = data.get(
        "hourly",
        {}
    )

    times = hourly.get(
        "time",
        []
    )

    velocities = hourly.get(
        "ocean_current_velocity",
        []
    )

    directions = hourly.get(
        "ocean_current_direction",
        []
    )

    index = _nearest_hour_index(
        times,
        dt
    )

    velocity = velocities[index]
    direction = directions[index]

    if (
        velocity is None
        or direction is None
    ):
        raise ValueError(
            "Ocean current data is unavailable "
            "for the requested time."
        )

    return {
        "speed_kmh": float(
            velocity
        ),
        "direction_deg": float(
            direction
        ),
        "timestamp": times[index],
        "provider": (
            "Open-Meteo Marine"
        ),
    }


def fetch_environment(
    latitude,
    longitude,
    observation_time
):
    """
    Fetch wind and ocean-current conditions
    for the requested spill location/time.
    """

    print()
    print(
        "=" * 60
    )

    print(
        "ENVIRONMENTAL DATA"
    )

    print(
        "=" * 60
    )

    print(
        "Location:",
        latitude,
        longitude
    )

    print(
        "Time:",
        observation_time
    )

    # --------------------------------------------------------
    # WIND
    # --------------------------------------------------------

    print(
        "Loading historical wind..."
    )

    wind = fetch_wind(
        latitude,
        longitude,
        observation_time
    )

    print(
        "Wind:",
        round(
            wind["speed_kmh"],
            2
        ),
        "km/h",
        "@",
        round(
            wind["direction_deg"],
            1
        ),
        "deg"
    )

    # --------------------------------------------------------
    # CURRENT
    # --------------------------------------------------------

    print(
        "Loading ocean current..."
    )

    current = fetch_current(
        latitude,
        longitude,
        observation_time
    )

    print(
        "Current:",
        round(
            current["speed_kmh"],
            2
        ),
        "km/h",
        "@",
        round(
            current["direction_deg"],
            1
        ),
        "deg"
    )

    return {
        "wind_speed_kmh": round(
            wind["speed_kmh"],
            3
        ),

        "wind_bearing_deg": round(
            wind["direction_deg"],
            2
        ),

        "current_speed_kmh": round(
            current["speed_kmh"],
            3
        ),

        "current_bearing_deg": round(
            current["direction_deg"],
            2
        ),

        "wind_timestamp": wind[
            "timestamp"
        ],

        "current_timestamp": current[
            "timestamp"
        ],

        "wind_provider": wind[
            "provider"
        ],

        "current_provider": current[
            "provider"
        ],

        "provider": (
            "Open-Meteo historical wind "
            "+ marine ocean-current model"
        ),

        "status": "REAL_MODELED_DATA",
    }
