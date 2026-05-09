import os
from types import SimpleNamespace
from dotenv import load_dotenv


def _parse_targets(raw: str) -> list[str]:
    result = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            raise ValueError(
                f"Invalid LINE_NOTIFY_TARGETS entry: {item!r} — expected 'type:id' format"
            )
        _, target_id = item.split(":", 1)
        result.append(target_id)
    return result


FIXED_LOCATION_NAME = "熊本市中央区横手3丁目"
FIXED_LOCATION_LAT = 32.8022
FIXED_LOCATION_LON = 130.7081


def load() -> SimpleNamespace:
    load_dotenv()
    targets = _parse_targets(os.environ["LINE_NOTIFY_TARGETS"])
    if not targets:
        raise ValueError(
            "LINE_NOTIFY_TARGETS must contain at least one valid 'type:id' entry"
        )
    return SimpleNamespace(
        LINE_CHANNEL_ACCESS_TOKEN=os.environ["LINE_CHANNEL_ACCESS_TOKEN"],
        LINE_NOTIFY_TARGETS=targets,
        LOCATION_NAME=FIXED_LOCATION_NAME,
        LOCATION_LAT=FIXED_LOCATION_LAT,
        LOCATION_LON=FIXED_LOCATION_LON,
        HOSHIMIRU_API_TOKEN=os.environ.get("HOSHIMIRU_API_TOKEN", ""),
        NASA_APOD_API_KEY=os.environ.get("NASA_APOD_API_KEY", "DEMO_KEY"),
        JMA_AREA_CODE=os.environ["JMA_AREA_CODE"],
        DEEPL_API_KEY=os.environ.get("DEEPL_API_KEY", ""),
    )
