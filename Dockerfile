FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
ENV PYTHONPATH=/app/src
RUN python -c "from skyfield.api import Loader; Loader('/app/skyfield-data')('de421.bsp')"
CMD ["uvicorn", "src.webhook:app", "--host", "0.0.0.0", "--port", "8080"]
