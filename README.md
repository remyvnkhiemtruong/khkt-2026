// FILE: README.md
# Cảnh báo sớm ngập úng – Case A (H–Q)

Hệ thống gồm ứng dụng desktop Windows (PyQt6) và firmware ESP8266/ESP32 đo mực nước (JSN‑SR04T) + mưa nhị phân (YL‑83), gửi telemetry JSON qua MQTT/HTTP. Ứng dụng tính H, H_eff, Q theo đường đặc tính H–Q, QC, dự báo 3–72h, cảnh báo theo rules.yaml, lưu SQLite, UI 5 tab, dialog hiệu chuẩn H–Q, và export CSV/PDF. Toàn bộ chạy offline trong LAN.

## Yêu cầu hệ thống
- Windows 10/11, Python >= 3.10
- MQTT broker trong LAN (mosquitto) nếu dùng MQTT; hoặc HTTP ingest (FastAPI)

## Cài đặt nhanh
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r app\requirements.txt
```

## Chạy ứng dụng
```powershell
python -m app.main
```
- Mặc định HTTP ingest bật trên 0.0.0.0:8088 (POST /ingest).
- MQTT subscribe topic: `cmau/flood/nodes/+/telemetry`.
- Cấu hình nhanh trong tab Settings: host/port MQTT, port HTTP, API key (nếu dùng weather).

## Telemetry JSON (Firmware ⇒ App)
```json
{
  "ts": "2025-11-03T09:15:00+07:00",
  "node_id": "CM-01",
  "s": { "dist_m": 0.83, "rain_bin": 1, "batt_v": 4.92 },
  "meta": { "sensor_height_above_crest_m": 0.95 },
  "ver": 2
}
```
Mapping: `H_m = sensor_height_above_crest_m − dist_m`, `H_eff = max(0, H_m − H0_m)`, `Q = a*(H_eff**b)`.

## UI & Tính năng
- Dashboard: rủi ro 3/6/9/12/24/48/72h, biểu đồ H(cm)/Q, 5 cảnh báo mới.
- Devices: bảng thiết bị (online, pin, last_seen …).
- Forecast: bảng dự báo theo chân trời.
- History/Report: export CSV/PDF.
- Settings: cấu hình MQTT/HTTP và API key.
- H–Q Calibration: import CSV (H,Q) → fit a,b,H0 (SciPy nếu có; fallback numpy grid+log-regression) → Áp dụng.

## SQLite schema
Xem `app/storage/db.py` — gồm các bảng: telemetry, forecast, hq_profile, alerts, devices, api_cache.

## Quy tắc QC
- OUT_OF_RANGE_DIST nếu dist_m ∉ [0.05, 5.0]
- NEG_H nếu H_m < −0.02
- SPIKES_H nếu |ΔH_10m| ≥ 0.15 m/10'
- OUT_OF_RANGE_Q nếu Q < 0 hoặc > Q_max (mặc định 1000)

## Cảnh báo (rules.yaml)
- Early (6h): prob ≥ 0.60 hoặc (ΔH_10m ≥ 0.08 & rain_next_hour ≥ 10 mm/h)
- High (12h): prob ≥ 0.70
- Hysteresis: 8% ; Debounce: 30 phút

## Firmware (Arduino .ino)
Thư mục `firmware/cmau_flood_node_caseA/`. Mở `cmau_flood_node_caseA.ino` với Arduino IDE.
- Board: ESP8266 (NodeMCU) hoặc ESP32
- Libraries: ArduinoJson, PubSubClient (nếu MQTT)
- Pinout JSN-SR04T: TRIG=D5(GPIO14)/18, ECHO=D6(GPIO12)/19 — lưu ý dùng chia áp ECHO 5V→3.3V
- Mưa YL-83 (digital): D7/ESP8266, 21/ESP32
- NTP TZ +07:00, median-of-5 mỗi 10s, gửi gộp mỗi 60s
- Chọn giao thức bằng macro `PROTOCOL_MQTT`
- Sửa Wi‑Fi, broker/HTTP endpoint ở đầu file.

## Hiệu chuẩn H–Q
1. Thu thập CSV có cột H, Q (đơn vị m, m³/s)
2. Mở dialog H–Q Calibration → Import CSV & Fit → xem R²/RMSE → Apply
3. Thông số được lưu vào bảng `hq_profile` theo `node_id`

## Test nhanh
```powershell
pytest -q
```

## Đóng gói (PyInstaller)
- Sử dụng PyInstaller `--onefile`/`--noconsole` và thêm dữ liệu theme.qss; nếu dùng WebEngine thì cần cấu hình bổ sung (không bắt buộc ở bản này).

## Troubleshooting
- MQTT không kết nối: kiểm tra host/port, firewall Windows, broker chạy chưa.
- HTTP ingest không nhận: cổng 8088 có bị chiếm; app đang chạy; POST đúng JSON schema.
- Không thấy H/Q: kiểm tra `sensor_height_above_crest_m` trong meta/hq_profile; dữ liệu `dist_m` hợp lệ.
- Fit thất bại: CSV thiếu cột H/Q hoặc dữ liệu không dương; thử bỏ giá trị bất thường.
- PDF lỗi font: đảm bảo reportlab cài đặt đúng; dùng ASCII/UTF-8 đơn giản.

## Giấy phép
MIT — xem file LICENSE.
# Flood Alert ML System

This repository contains the Flood Alert ML System Python project under `flood_alert_ml/`.

See `flood_alert_ml/README.md` for full documentation and usage.
