# Flood Alert ML System

A non-blocking PyQt6 desktop app that aggregates precipitation from Open-Meteo, OpenWeather, and a Simulator, computes consensus, and predicts flood risk using logistic regression models for instantaneous and multi-horizon windows.

## Features
- Responsive PyQt6 UI (all I/O and ML off UI thread)
- Parallel data fetch with retries/backoff and short-lived caching
- DQA and median aggregation with consensus score
- Instant and horizon ML models (3/6/9/12/24h)
- Windows location with WinRT + IP fallback
- Reverse geocoding via Open-Meteo
- Append-safe CSV and Excel logging
- Headless CLI mode

## Setup
1) Install Python 3.10+
2) Create venv and install requirements
3) Create a `.env` with `OPENWEATHER_API_KEY=...`

## Run
- GUI: `python -m flood_alert_ml`
- CLI (headless): `python -m flood_alert_ml.cli --lat 10.7626 --lon 106.6601 --interval 5 --headless`

Logs are written to `logs/flood_alert_log.csv` and `logs/flood_alert_log.xlsx` with a fixed schema.

## Notes
- This is a reference implementation with pragmatic defaults. You can toggle sources and update thresholds within the app.
- The UI applies a dark theme from `ui/styles.qss`.