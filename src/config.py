import os
from types import SimpleNamespace
from dotenv import load_dotenv


def load() -> SimpleNamespace:
    load_dotenv()
    return SimpleNamespace(
        LINE_CHANNEL_ACCESS_TOKEN=os.environ["LINE_CHANNEL_ACCESS_TOKEN"],
        LINE_USER_ID=os.environ["LINE_USER_ID"],
        LOCATION_LAT=float(os.environ["LOCATION_LAT"]),
        LOCATION_LON=float(os.environ["LOCATION_LON"]),
    )
