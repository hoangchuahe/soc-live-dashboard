# ---- Stage 1: build the React SPA ----
FROM node:20-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python runtime serving API + WS + SPA ----
FROM python:3.12-slim AS runtime
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
# Detection rules must land at /app/detections — the loader resolves
# Path(__file__).parents[2]/detections, i.e. /app/detections in this image.
COPY backend/detections ./detections
# Built SPA is served by FastAPI from /app/static (see STATIC_DIR below).
COPY --from=frontend /build/dist ./static
ENV SOC_MODE=demo \
    STATIC_DIR=/app/static \
    ELASTICSEARCH_URL=""
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
