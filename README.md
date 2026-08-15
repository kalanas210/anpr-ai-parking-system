# ANPR AI Parking System

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.1-000000?logo=flask&logoColor=white)
![YOLOv8](https://img.shields.io/badge/YOLOv8-Ultralytics-00FFFF?logo=yolo&logoColor=black)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-412991?logo=openai&logoColor=white)
![Roboflow](https://img.shields.io/badge/Roboflow-Inference-6706CE?logo=roboflow&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-4.12-5C3EE8?logo=opencv&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-47A248?logo=mongodb&logoColor=white)
![Node.js](https://img.shields.io/badge/Node.js-Express-339933?logo=nodedotjs&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![Stripe](https://img.shields.io/badge/Stripe-Payments-635BFF?logo=stripe&logoColor=white)
![Socket.IO](https://img.shields.io/badge/Socket.IO-realtime-010101?logo=socketdotio&logoColor=white)
![ESP32](https://img.shields.io/badge/ESP32-P10%20LED-E7352C?logo=espressif&logoColor=white)
![License](https://img.shields.io/badge/License-GPLv3-blue.svg)

> **Drive in, get recognized, park.** A vehicle pulls up to a slot, a camera reads its number
> plate in real time, the system checks it against the live booking, updates a roadside LED
> display, and logs the visit — end to end, with no attendant in the loop.

**ANPR AI Parking System** is an end-to-end **Automatic Number Plate Recognition (ANPR)** and
smart-parking platform. It fuses computer vision, a cloud OCR pipeline, an IoT LED display, and a
full booking-and-payments web app into one system. A YOLOv8 model detects vehicles inside
polygon-defined parking slots, Roboflow localizes the plate, and either **EasyOCR** or
**OpenAI GPT-4o-mini** reads the characters. Recognized plates are matched against active bookings,
slot status is pushed live to a web dashboard over Socket.IO, and an **ESP32-driven P10 LED matrix**
shows occupancy and raises an alarm for unauthorized vehicles.

---

## ✨ Highlights

- **Real-time ANPR** — YOLOv8 vehicle detection → Roboflow plate localization → dual OCR engines
  (EasyOCR on-device, or OpenAI GPT-4o-mini vision) with confidence gating.
- **Robust low-light recognition** — CLAHE contrast enhancement, bilateral denoising, adaptive/Otsu
  thresholding, morphological cleanup and upscaling before OCR.
- **Two run modes** — live **RTSP camera** mode for production, and an offline **video-file** mode
  so the whole pipeline can be demoed without any hardware.
- **Booking-aware** — recognized plates are validated against active bookings; OCR failures are
  handled gracefully so they don't raise false "unauthorized vehicle" alarms.
- **IoT feedback loop** — an ESP32 + P10 LED matrix shows per-slot status and sounds an alarm,
  controlled over a simple authenticated HTTP API.
- **Full booking web app** — React frontend + Node/Express API with JWT auth, Stripe checkout,
  SMS notifications, and an admin dashboard.
- **Secrets-clean** — every credential is loaded from environment variables; nothing sensitive is
  committed (see [`docs/SECURITY.md`](docs/SECURITY.md)).

---

## 🧩 Architecture

```
                        ┌──────────────────────────────────────────────┐
                        │              Detection service               │
   RTSP camera  ─────▶  │  YOLOv8 (vehicles) → Roboflow (plate box) →   │
   or video file        │  EasyOCR / OpenAI GPT-4o-mini (plate text)    │
                        └───────┬───────────────┬───────────────┬──────┘
                                │               │               │
                     Socket.IO  │      HTTP     │      HTTP      │  HTTP (auth key)
                                ▼               ▼               ▼
                     ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
                     │ Web dashboard│   │ Booking API  │   │  ESP32 + P10 │
                     │ (Flask/JS)   │   │ (Node/React) │   │  LED display │
                     └──────────────┘   └──────┬───────┘   └──────────────┘
                                               │
                                        ┌──────▼───────┐
                                        │ MongoDB Atlas │
                                        └──────────────┘
```

A deeper write-up lives in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), and the HTTP API is
documented in [`docs/API.md`](docs/API.md).

---

## 🛠️ Tech stack

| Layer | Technologies |
|-------|--------------|
| **Computer vision** | Python, OpenCV, Ultralytics YOLOv8, Roboflow Inference, EasyOCR, OpenAI GPT-4o-mini |
| **Detection backend** | Flask, Flask-SocketIO, Flask-CORS, PyMongo |
| **Booking backend** | Node.js, Express, Mongoose, JWT, bcryptjs, Stripe, express-validator |
| **Frontend** | React 18, React Router, Axios, Stripe.js; Flask/Jinja dashboard |
| **Data** | MongoDB Atlas |
| **IoT / hardware** | ESP32 (Arduino), DMD32 P10 LED matrix, I2S audio alarm |

---

## 📂 Repository layout

```
anpr-ai-parking-system/
├── detection/            # Python computer-vision + Flask service
│   ├── app.py            #   RTSP / live-camera mode (entry point)
│   ├── app_video.py      #   offline video-file / demo mode
│   ├── livedetect*.py    #   EasyOCR detection pipelines
│   ├── openai_smart*.py  #   OpenAI GPT-4o-mini OCR pipelines
│   ├── config*.py        #   configuration (loads secrets from .env)
│   ├── templates/        #   Flask dashboard (login + index)
│   ├── scripts/          #   start_system / start_video_system launchers
│   └── .env.example
├── booking-system/       # Booking web app
│   ├── server/           #   Node.js + Express API  (.env.example)
│   └── client/           #   React frontend          (.env.example)
├── arduino/              # ESP32 firmware for the P10 LED display
│   ├── p10_code.ino
│   └── PageIndex.h
├── docs/                 # Architecture, API, and security docs
├── LICENSE
└── README.md
```

---

## 🚀 Quick start

> **Prerequisites:** Python 3.8+, Node.js 16+, a MongoDB Atlas connection string, an OpenAI API key,
> a Roboflow API key, and (optional) Stripe test keys. The YOLOv8 weights (`yolov8n.pt`) download
> automatically on first run.

### 1. Detection service

```bash
cd detection
python -m venv venv
venv\Scripts\activate            # Windows  (use: source venv/bin/activate on macOS/Linux)
pip install -r requirements.txt

cp .env.example .env             # then edit .env and fill in your credentials
python app.py                    # live RTSP mode  → http://localhost:5000
# or
python app_video.py              # offline video-file / demo mode
```

### 2. Booking system

```bash
cd booking-system/server
npm install
cp .env.example .env             # then edit .env (MongoDB, JWT, Stripe…)
npm run dev                      # API on http://localhost:5001

# in another terminal:
cd booking-system/client
npm install
cp .env.example .env             # then edit .env (API URL, Stripe publishable key)
npm start                        # React app on http://localhost:3000
```

### 3. P10 LED display (optional hardware)

Open `arduino/p10_code.ino` in the Arduino IDE, set your WiFi SSID/password and the display auth
key, then flash it to the ESP32. Point `ESP32_IP` / `ESP32_KEY` in `detection/.env` at the device.

---

## 🔐 Configuration & secrets

All credentials are read from environment variables — **no secrets are committed**. Each component
ships an `.env.example`; copy it to `.env` and fill in your own values:

| File | Holds |
|------|-------|
| `detection/.env` | MongoDB URI, RTSP URL, OpenAI & Roboflow keys, ESP32 IP/key |
| `booking-system/server/.env` | MongoDB URI, JWT secret, Stripe keys, SMS gateway creds |
| `booking-system/client/.env` | API URL, Stripe **publishable** key |

`.env` files are git-ignored. See [`docs/SECURITY.md`](docs/SECURITY.md) for the full secret list and
a key-rotation checklist.

---

## 🗺️ Roadmap / known limitations

This started as a university final-year project; a few areas are intentionally left as next steps:

- Some booking endpoints used by the detection service (`/api/slots/status`,
  `/api/bookings/active`) are currently unauthenticated — they should be protected with an
  API key or service token before any public deployment.
- The Stripe webhook handler and the `autoCompletion` cron service need wiring/hardening for
  production (see `docs/ARCHITECTURE.md`).
- `enhanced_exit_detection.py` (motion + occlusion based exit detection) is implemented but not yet
  wired into the live pipeline, which uses simpler buffer-based exit logic.

---

## 👥 Team & my role

Built by **NexGen Innovators** as a final-year group project.

> _**My contribution (Kalana Sandakelum):** TODO — replace with 1–3 lines on what you personally
> owned, e.g. "Designed and built the computer-vision ANPR pipeline (YOLOv8 + Roboflow + OpenAI OCR)
> and the real-time Flask/Socket.IO dashboard."_

---

## 📄 License

Released under the [GNU General Public License v3.0](LICENSE).

Copyright (C) 2025 Kalana Sandakelum.
