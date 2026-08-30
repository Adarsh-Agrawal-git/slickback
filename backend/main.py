import os
from pathlib import Path
from datetime import datetime, timedelta

from dotenv import load_dotenv

# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv(BASE_DIR / ".env")

# ============================================================
# IMPORT APPLICATION MODULES
# ============================================================

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from pipeline import run_pipeline
from satellite.ais_live import refresh_live_ais


# ============================================================
# DATA DIRECTORY
# ============================================================

DATA_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="SlickBack API",
    version="1.0.0",
)
# ============================================================
# SERVE ANALYSIS FILES
# ============================================================

app.mount(
    "/analysis-files",
    StaticFiles(
        directory=str(DATA_DIR)
    ),
    name="analysis-files",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# REQUEST MODEL
# ============================================================

class SpillRequest(BaseModel):

    spill_lat: float = Field(
        ...,
        ge=-90,
        le=90,
    )

    spill_lon: float = Field(
        ...,
        ge=-180,
        le=180,
    )

    observation_time: datetime

    hours_back: int = Field(
        default=6,
        ge=1,
        le=48,
    )


# ============================================================
# HEALTH / ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "name": "SlickBack",
        "status": "running",
        "version": "1.0.0",
    }


@app.get("/health")
def health():

    return {
        "status": "ok",
    }


# ============================================================
# ANALYZE SPILL
# ============================================================

@app.post("/analyze-spill")
def analyze_spill(
    request: SpillRequest,
):

    # --------------------------------------------------------
    # DATA PATHS
    # --------------------------------------------------------

    vessel_data_path = os.getenv(
        "VESSEL_DATA_PATH",
        str(DATA_DIR / "vessels.csv"),
    )

    ais_history_path = os.getenv(
        "AIS_HISTORY_PATH",
        str(DATA_DIR / "ais_history.csv"),
    )

    image_output_path = os.getenv(
        "SENTINEL1_OUTPUT_PATH",
        str(DATA_DIR / "sentinel1_vv.tif"),
    )

    # --------------------------------------------------------
    # CONFIGURATION
    # --------------------------------------------------------

    bbox_delta = float(
        os.getenv(
            "SENTINEL1_BBOX_DELTA",
            "0.10",
        )
    )

    image_size = int(
        os.getenv(
            "SENTINEL1_IMAGE_SIZE",
            "800",
        )
    )

    radius_km = float(
        os.getenv(
            "AIS_RADIUS_KM",
            "50",
        )
    )

    min_candidate_area = int(
        os.getenv(
            "MIN_CANDIDATE_AREA",
            "10",
        )
    )

    ais_duration = int(
        os.getenv(
            "AIS_COLLECTION_SECONDS",
            "30",
        )
    )

    # --------------------------------------------------------
    # TIME WINDOW
    # --------------------------------------------------------

    start_datetime = (
        request.observation_time
        - timedelta(
            hours=request.hours_back
        )
    )

    end_datetime = request.observation_time

    # ========================================================
    # STEP 4
    # REFRESH LIVE AIS DATA
    # ========================================================

    ais_refresh_result = None

    try:

        ais_refresh_result = refresh_live_ais(
            latitude=request.spill_lat,
            longitude=request.spill_lon,
            radius_km=radius_km,
            vessels_path=vessel_data_path,
            history_path=ais_history_path,
            duration_seconds=ais_duration,
        )

        print(
            "LIVE AIS REFRESH COMPLETE:"
        )

        print(
            ais_refresh_result
        )

    except Exception as error:

        error_text = str(error)

        if "AISSTREAM_API_KEY is not set" in error_text:

            reason = (
                "AISStream API key not configured"
            )

        else:

            reason = error_text

        print(
            "Live AIS unavailable:",
            reason,
        )

        ais_refresh_result = {

            "enabled": True,

            "available": False,

            "status": "unavailable",

            "provider": "AISStream",

            "reason": reason,

            "vessels_received": 0,
        }

    # ========================================================
    # RUN PIPELINE
    # ========================================================

    try:

        result = run_pipeline(

            latitude=request.spill_lat,

            longitude=request.spill_lon,

            start_datetime=(
                start_datetime.isoformat()
            ),

            end_datetime=(
                end_datetime.isoformat()
            ),

            hours_back=request.hours_back,

            vessel_data_path=(
                vessel_data_path
            ),

            ais_history_path=(
                ais_history_path
            ),

            observation_time=(
                request.observation_time.isoformat()
            ),

            image_output_path=(
                image_output_path
            ),

            radius_km=radius_km,

            bbox_delta=bbox_delta,

            image_size=image_size,

            min_candidate_area=(
                min_candidate_area
            ),
        )

        # ----------------------------------------------------
        # ATTACH LIVE AIS INFORMATION
        # ----------------------------------------------------

        if isinstance(result, dict):

            result["live_ais"] = (
                ais_refresh_result
            )

            # ------------------------------------------------
            # SENTINEL-1 IMAGE URL
            # ------------------------------------------------

            satellite = result.get(
                "satellite"
            )

            if isinstance(
                satellite,
                dict
            ):

                image_path = satellite.get(
                    "image_path"
                )

                if image_path:

                    image_name = Path(
                        image_path
                    ).name

                    satellite["image_url"] = (
                        "/analysis-files/"
                        + image_name
                    )

        return result

    except Exception as error:

        print(
            "\n========== PIPELINE ERROR =========="
        )

        print(
            str(error)
        )

        print(
            "====================================\n"
        )

        raise HTTPException(
            status_code=500,
            detail=str(error),
        )