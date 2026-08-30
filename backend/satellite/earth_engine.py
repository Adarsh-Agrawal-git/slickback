from pathlib import Path

import ee
from google.oauth2 import service_account


BASE_DIR = Path(__file__).resolve().parent.parent

PROJECT_ID = "slickback-507020"
KEY_FILE = BASE_DIR / "slickback-earthengine.json"


def initialize_earth_engine():
    credentials = service_account.Credentials.from_service_account_file(
        str(KEY_FILE),
        scopes=[
            "https://www.googleapis.com/auth/earthengine",
            "https://www.googleapis.com/auth/cloud-platform",
        ],
    )

    ee.Initialize(
        credentials=credentials,
        project=PROJECT_ID,
    )