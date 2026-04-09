# Zentraly – Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/release/sebastianpagano/ha-zentraly.svg)](https://github.com/sebastianpagano/ha-zentraly/releases)

Custom integration for [Home Assistant](https://www.home-assistant.io/) to control **Zentraly WiFi thermostats** (boiler controllers).

Supports reading temperature, humidity, and boiler state, as well as setting the target temperature and switching modes on/off.

---

## Features

- Current room temperature and humidity
- Target temperature control (5 °C – 35 °C, 0.5 °C steps)
- HVAC modes: **Heat** / **Off**
- Extra attributes: WiFi signal (RSSI), firmware version, boiler output state
- Auto-discovers all thermostats linked to your account
- Token-based auth with automatic re-login

---

## Installation

### Via HACS (recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations → ⋮ → Custom repositories**
3. Add `https://github.com/sebastianpagano/ha-zentraly` — category **Integration**
4. Search for **Zentraly** and install
5. Restart Home Assistant

### Manual

1. Copy `custom_components/zentraly/` into your HA config folder:
   ```
   /config/custom_components/zentraly/
   ```
2. Restart Home Assistant

---

## Configuration

Go to **Settings → Devices & Integrations → Add Integration → Zentraly**.

Enter your Zentraly account email and password. The integration will discover all thermostats linked to your account.

---

## API (reverse-engineered via MITM)

| Endpoint | Method | Description |
|---|---|---|
| `/Login` | GET | Auth with `Authorization: ztv2Auth{email}:{password}` → returns JWT |
| `/App` | POST | Lists locations, zones and devices |
| `/IOTCommand/Run` | POST | `getConfig` / `setConfig` commands to the thermostat |

### Read state
```json
POST /IOTCommand/Run
{
  "deviceId": "ZTTWF0100009124",
  "timeOut": 15000,
  "data": {
    "cmd": "getConfig",
    "rid": 1,
    "ids": ["targetTemp", "temperature", "thermostatMode", "humidity", "rssi", "output"]
  }
}
```
Response (temperature in centidegrees, e.g. `2310` = 23.1 °C):
```json
{"ids":[{"targetTemp":2550},{"temperature":2310},{"thermostatMode":4},{"humidity":64},{"output":1}],"status":200}
```

### Set temperature
```json
{"deviceId":"ZTTWF0100009124","timeOut":15000,"data":{"cmd":"setConfig","rid":0,"ids":[{"targetTemp":2200}]}}
```

### Set mode
```json
{"deviceId":"ZTTWF0100009124","timeOut":15000,"data":{"cmd":"setConfig","rid":0,"ids":[{"thermostatMode":0}]}}
```

| `thermostatMode` | HA mode | Notes |
|---|---|---|
| `0` | `off` | Confirmed via MITM |
| `4` | `heat` | "Modo manual" – confirmed via MITM |

---

## Supported languages

- English (`en`)
- Spanish (`es`)
- Portuguese (`pt`)

---

## License

MIT
