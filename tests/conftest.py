import os
import pathlib

# astro_events.py hardcodes /app/skyfield-data; create it if missing so tests
# can collect without PermissionError on non-Docker environments.
skyfield_dir = pathlib.Path("/app/skyfield-data")
try:
    skyfield_dir.mkdir(parents=True, exist_ok=True)
except PermissionError:
    import tempfile
    alt = pathlib.Path(tempfile.gettempdir()) / "app" / "skyfield-data"
    alt.mkdir(parents=True, exist_ok=True)
    src = pathlib.Path("/tmp/skyfield-data")
    if src.exists():
        import shutil
        for f in src.iterdir():
            dest = alt / f.name
            if not dest.exists():
                shutil.copy2(f, dest)
    os.environ.setdefault("SKYFIELD_DATA_PATH", str(alt))
