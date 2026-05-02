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
        LOCATION_LAT=float(os.environ["LOCATION_LAT"]),
        LOCATION_LON=float(os.environ["LOCATION_LON"]),
        HOSHIMIRU_API_TOKEN=os.environ.get("HOSHIMIRU_API_TOKEN", ""),
    )
