import os
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from pipeline import run_pipeline


app = FastAPI(
    title="SlickBack API",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SpillRequest(BaseModel):
    spill_lat: float = Field(..., ge=-90, le=90)
    spill_lon: float = Field(..., ge=-180, le=180)
    observation_time: datetime
    hours_back: int = Field(
        default=6,
        ge=1,
        le=48
    )


@app.get("/")
def root():
    return {
        "name": "SlickBack",
        "status": "running"
    }


@app.get("/health")
def health():
    return {
        "status": "ok"
    }


@app.post("/analyze-spill")
def analyze_spill(request: SpillRequest):

    vessel_data_path = os.getenv(
        "VESSEL_DATA_PATH",
        "data/vessels.csv"
    )

    image_output_path = os.getenv(
        "SENTINEL1_OUTPUT_PATH",
        "data/sentinel1_vv.tif"
    )

    bbox_delta = float(
        os.getenv("SENTINEL1_BBOX_DELTA", "0.10")
    )

    image_size = int(
        os.getenv("SENTINEL1_IMAGE_SIZE", "800")
    )

    radius_km = float(
        os.getenv("AIS_RADIUS_KM", "50")
    )

    min_candidate_area = int(
        os.getenv("MIN_CANDIDATE_AREA", "10")
    )

    start_datetime = (
        request.observation_time
        - timedelta(hours=request.hours_back)
    )

    end_datetime = request.observation_time

    try:

        result = run_pipeline(
    latitude=request.spill_lat,
    longitude=request.spill_lon,
    start_datetime=start_datetime.isoformat(),
    end_datetime=end_datetime.isoformat(),
    hours_back=request.hours_back,
    vessel_data_path=vessel_data_path,
    image_output_path=image_output_path,
    radius_km=radius_km,
    bbox_delta=bbox_delta,
    image_size=image_size,
    min_candidate_area=min_candidate_area,
)

        return result

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error)
        )