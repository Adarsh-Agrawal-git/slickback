import os
import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("CDSE_CLIENT_ID")
CLIENT_SECRET = os.getenv("CDSE_CLIENT_SECRET")

TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu/"
    "auth/realms/CDSE/protocol/openid-connect/token"
)


def get_access_token():
    if not CLIENT_ID or not CLIENT_SECRET:
        raise RuntimeError(
            "CDSE_CLIENT_ID or CDSE_CLIENT_SECRET is missing from .env"
        )

    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        timeout=120,
    )

    response.raise_for_status()

    return response.json()["access_token"]