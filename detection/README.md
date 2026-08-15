# Detection Service

The Python computer-vision service for the ANPR AI Parking System. It detects
vehicles in a camera feed or video file, reads license plates, tracks per-slot
occupancy, persists records to MongoDB, pushes live updates to the web dashboard
over Socket.IO, and (optionally) drives a P10 LED display via an ESP32.

Vehicle detection uses Ultralytics YOLOv8 (`yolov8n.pt`). License-plate
localization uses a hosted Roboflow model, and plate text is read by either
EasyOCR (local) or OpenAI's `gpt-4o-mini` vision model.

## Prerequisites

- **Python 3.8+**
- A MongoDB instance (the code targets MongoDB Atlas, database `parking_system`)
- The environment variables defined in [`.env.example`](.env.example):
  - `MONGO_URI`, `DB_NAME`
  - `RTSP_URL`, `VIDEO_SOURCE`
  - `OPENAI_API_KEY`, `ROBOFLOW_API_KEY`, `LICENSE_PLATE_MODEL_ID`
  - `HOST`, `PORT`, `FLASK_DEBUG`, `FLASK_SECRET_KEY`
  - `P10_ENABLED`, `ESP32_IP`, `ESP32_KEY`
  - `LOG_LEVEL`

> Never commit your real `.env`. Reference variable **names** only — keep
> credentials out of source control.

## Setup

```bash
# from the detection/ directory

# 1. Create and activate a virtual environment
python -m venv venv
# Windows
venv\Scripts\activate
# Linux / macOS
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure secrets
cp .env.example .env      # Windows: copy .env.example .env
# then open .env and fill in your own values
```

On the first run, Ultralytics downloads the `yolov8n.pt` weights automatically
into the working directory — no manual download step is required.

## Run modes

There are two entry points. Both serve the dashboard on
`http://localhost:5000` (configurable via `HOST`/`PORT`) and expose the same
REST + Socket.IO API.

### Live / RTSP mode — `app.py`

Processes a live camera stream. Set `RTSP_URL` in `.env` (e.g.
`rtsp://<user>:<pass>@<host>:554/Streaming/Channels/101`). `VIDEO_SOURCE`
defaults to `RTSP_URL`, so leaving `VIDEO_SOURCE` empty uses the live stream.

```bash
python app.py
```

### Offline / demo mode — `app_video.py`

Processes a local video file instead of a live feed. Set `VIDEO_SOURCE` to the
path of a video file on disk (place the clip alongside the detection scripts and
point `VIDEO_SOURCE` at it).

```bash
python app_video.py
```

## OCR engine selection

The active OCR engine is held in the in-memory `current_ocr_method` variable
(default `"EasyOCR"`). Switch it at runtime by POSTing to `/api/switch-ocr`
with `{"method": "EasyOCR"}` or `{"method": "OpenAI"}`; the choice is also
recorded in the `system_status` collection.

The detection loop does not run inference inline — it launches a worker script
as a **subprocess** (in a new console window on Windows) based on the selected
engine:

| Mode | EasyOCR worker | OpenAI worker |
|------|----------------|---------------|
| `app.py` (live) | `livedetect.py` | `openai_smart.py` |
| `app_video.py` (demo) | `livedetect_video.py` | `openai_smart_video.py` |

The worker writes per-slot state to `slot_status.json` and saves crops into the
`debug_cars`, `debug_plates`, and `error_vehicles` folders. The parent app polls
that JSON file to update occupancy, persist parking records, and emit live
updates to the dashboard.

## Configuration reference

These are the important settings in [`config.py`](config.py) (live mode). The
demo equivalent is [`config_video.py`](config_video.py), which uses different
slot polygons and a simpler OCR-retry block.

| Setting | Default | Purpose |
|---------|---------|---------|
| `PARKING_SLOTS` | two 4-point polygons | Slot regions as polygon coordinates on the resized `1020x500` frame |
| `OCR_TRIGGER_DELAY` | `10` | Seconds a vehicle must stay parked before OCR fires (live mode) |
| `OCR_RETRY_INTERVAL` | `8` | Seconds between OCR retries (live mode) |
| `MAX_OCR_ATTEMPTS` | `4` | Maximum OCR attempts per vehicle (live mode) |
| `CAR_DETECTION_CONFIDENCE` | `0.5` | Minimum YOLO confidence to accept a vehicle |
| `LICENSE_PLATE_CONFIDENCE` | `0.4` | Minimum Roboflow confidence to accept a plate box |
| `MIN_CONFIDENCE` | `0.3` | Minimum OCR text confidence |
| `VEHICLE_CLASSES` | `car, truck, bus, motorcycle` | YOLO classes treated as vehicles |
| `LICENSE_PLATE_PATTERN` | `^[A-Z]{2,3}\s*[0-9]{4}$` | Sri Lankan plate format validation |
| `VIDEO_RESIZE_WIDTH` / `VIDEO_RESIZE_HEIGHT` | `1020` / `500` | Frame size the slot polygons are defined against |
| `ESP32_IP` | env `ESP32_IP` | IP of the ESP32 driving the P10 LED display |
| `ESP32_KEY` | env `ESP32_KEY` | Auth key that must match the ESP32 firmware |
| `P10_ENABLED` | env `P10_ENABLED` | Enable/disable the P10 LED display integration |

> The demo config ([`config_video.py`](config_video.py)) uses `DEFAULT_OCR_METHOD`,
> `OCR_RETRY_ATTEMPTS`, and `OCR_DELAY_BETWEEN_ATTEMPTS` instead of the live
> mode's `OCR_TRIGGER_DELAY` / `OCR_RETRY_INTERVAL` / `MAX_OCR_ATTEMPTS`.

## Convenience launchers

The [`scripts/`](scripts) folder contains cross-platform launchers. Each one
`cd`s into `detection/`, checks for Python and a `.env` file, then starts the
matching app. The Windows `.bat` for live mode also runs
`pip install -r requirements.txt` before launching.

| Script | Platform | Launches |
|--------|----------|----------|
| `scripts/start_system.bat` | Windows | `app.py` (live / RTSP) |
| `scripts/start_system.sh` | Linux / macOS | `app.py` (live / RTSP) |
| `scripts/start_video_system.bat` | Windows | `app_video.py` (video / demo) |
| `scripts/start_video_system.sh` | Linux / macOS | `app_video.py` (video / demo) |

Example:

```bash
# live mode
scripts/start_system.sh

# demo mode
scripts/start_video_system.sh
```

Once running, open the dashboard at `http://localhost:5000` and use the
**Start Detection** control (or POST `/api/start-detection`) to begin
processing.
