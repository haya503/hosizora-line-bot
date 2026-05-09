import os
import pathlib

# astro_events.py hardcodes /app/skyfield-data; create it if missing so tests
# can collect without PermissionError on non-Docker environments.
skyfield_dir = pathlib.Path("/app/skyfield-data")
try:
    skyfield_dir.mkdir(parents=True, exist_ok=True)
except PermissionError:
    # Fall back to a writable temp location and monkey-patch the path via env
    import tempfile
    alt = pathlib.Path(tempfile.gettempdir()) / "app" / "skyfield-data"
    alt.mkdir(parents=True, exist_ok=True)
    # Copy any existing .bsp files from /tmp/app/skyfield-data if available
    src = pathlib.Path("/tmp/app/skyfield-data")
    if src.exists():
        import shutil
        for f in src.iterdir():
            dest = alt / f.name
            if not dest.exists():
                shutil.copy2(f, dest)
    # Patch astro_events module path before it is imported
    os.environ.setdefault("SKYFIELD_DATA_PATH", str(alt))
