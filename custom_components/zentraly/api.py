"""Zentraly API client.

Protocolo documentado via MITM (mitmproxy) del tráfico de la app Android.

Auth flow:
  GET /Login
    Authorization: ztv2Auth{email}:{password}
    firebase: <base64 JSON con metadata del dispositivo>
  → devuelve JWT token + lista de ubicaciones/dispositivos

Comandos (todos POST /IOTCommand/Run):
  getConfig  → lee estado actual del termostato
  setConfig  → escribe targetTemp o thermostatMode

Temperatura: API usa centigrados × 100 (ej: 21.5°C = 2150)
"""

from __future__ import annotations

import base64
import json
import logging
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from typing import Optional

from .const import (
    COMMAND_TIMEOUT,
    IOT_COMMAND_URL,
    LOGIN_URL,
    TEMP_SCALE,
)

_LOGGER = logging.getLogger(__name__)

_FIREBASE_HEADER_TEMPLATE = {
    "ivstrUserFBToken": "ha_token",
    "ivstrUserGuid": "ha_token",
    "ivstrUserZtVersion": "6.3.0",
    "ivnroUserMobileOS": 1,          # 1 = iOS, 2 = Android
    "ivstrUserMobileTrade": "apple",
    "ivstrUserMobileModel": "iPhone14,3",  # iPhone 13 Pro Max
    "ivstrUserMobileOSVersion": 17,
    "ivstrUserLanguage": "es",
}

# iOS app uses CFNetwork / NSURLSession, not okhttp
_IOS_USER_AGENT = (
    "Zentraly/6.3.0 (com.kotlin.zentraly; build:1; iOS 17.4.1)"
    " CFNetwork/1494.0.7 Darwin/23.4.0"
)


def _make_firebase_header() -> str:
    return base64.b64encode(
        json.dumps(_FIREBASE_HEADER_TEMPLATE).encode()
    ).decode()


def _request(url: str, *, method: str = "GET", headers: dict, body: Optional[dict] = None) -> dict:
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode(errors="ignore")[:200]
        if exc.code in (401, 403):
            raise ZentralyAuthError(f"HTTP {exc.code}: {body_text}") from exc
        raise ZentralyConnectionError(f"HTTP {exc.code}: {body_text}") from exc
    except Exception as exc:
        raise ZentralyConnectionError(str(exc)) from exc


class ZentralyAuthError(Exception):
    """Authentication or authorization error."""


class ZentralyConnectionError(Exception):
    """Network or connection error."""


class ZentralyAPI:
    """Client for the Zentraly REST API."""

    def __init__(self, email: str, password: str) -> None:
        self._email = email
        self._password = password
        self._token: Optional[str] = None
        self._token_expires: datetime = datetime.min
        self._firebase_header = _make_firebase_header()
        self._login_data: dict = {}  # full login response, parsed once

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _common_headers(self, *, auth_token: str | None = None) -> dict:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Accept-Language": "es-AR;q=1.0, en-AR;q=0.9",
            "firebase": self._firebase_header,
            "authorization": auth_token or f"ztv2Auth{self._email}:{self._password}",
            "User-Agent": _IOS_USER_AGENT,
        }

    def login(self) -> dict:
        """Authenticate and return the full login payload."""
        _LOGGER.debug("Logging in to Zentraly as %s", self._email)
        result = _request(LOGIN_URL, headers=self._common_headers())
        if result.get("numStatus") != 0:
            raise ZentralyAuthError(f"Login failed: numStatus={result.get('numStatus')}")

        # Token is at ioData.ivstrToken (confirmed via MITM capture)
        io_data = result.get("ioData", {})
        token_raw = io_data.get("ivstrToken")
        if not token_raw:
            _LOGGER.error("Could not find ivstrToken in login response: %s", json.dumps(result)[:500])
            raise ZentralyAuthError("Login succeeded but token not found in response")

        self._token = token_raw
        self._login_data = io_data  # cache for device discovery
        # JWT expires in ~100 years based on captured token (exp: 2121297637)
        self._token_expires = datetime.now() + timedelta(hours=23)
        return result

    def _auth_token_header(self) -> str:
        if self._token:
            return f"ztv2Token{self._token}"
        return f"ztv2Auth{self._email}:{self._password}"

    def ensure_authenticated(self) -> None:
        """Re-login if token is missing or expired."""
        if not self._token or datetime.now() >= self._token_expires:
            self.login()

    # ------------------------------------------------------------------
    # Device discovery
    # ------------------------------------------------------------------

    def get_devices(self) -> list[dict]:
        """Return list of thermostat devices for this account.

        Parses the device list from the login response (already cached),
        so no extra network call is needed.
        """
        self.ensure_authenticated()
        ubications = (
            self._login_data
            .get("ioUser", {})
            .get("coUbications", [])
        )
        devices = []
        for ubication in ubications:
            ub_name = ubication.get("ioDCModel", {}).get("ivstrUbicationName", "")
            for zone in ubication.get("coZones", []):
                zone_name = zone.get("ioDCModel", {}).get("ivstrZoneName", "")
                for device in zone.get("coDevices", []):
                    model = device.get("ioDCModel", {})
                    sub = device.get("ioSubTypeObj", {}).get("ioDCModel", {})
                    dev_name = model.get("ivstrDeviceName", model.get("ivstrDeviceSerial", ""))
                    devices.append({
                        "device_id": model.get("ivstrDeviceSerial"),
                        "name": f"{ub_name} – {zone_name} – {dev_name}",
                        "connected": model.get("ivblnDeviceConnected", False),
                        "firmware": model.get("ivstrDeviceFWVersion"),
                        "ubication": ub_name,
                        "zone": zone_name,
                        "sub": sub,
                    })
        return devices

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    def get_state(self, device_id: str) -> dict:
        """Read current thermostat state. Returns parsed values."""
        self.ensure_authenticated()
        body = {
            "deviceId": device_id,
            "timeOut": COMMAND_TIMEOUT,
            "data": {
                "cmd": "getConfig",
                "rid": 1,
                "ids": [
                    "targetTemp",
                    "temperature",
                    "thermostatMode",
                    "humidity",
                    "rssi",
                    "vs",
                    "output",
                    "tAway",
                    "lock",
                    "service",
                ],
            },
        }
        result = _request(
            IOT_COMMAND_URL,
            method="POST",
            headers=self._common_headers(auth_token=self._auth_token_header()),
            body=body,
        )
        if result.get("numStatus") != 0:
            raise ZentralyConnectionError(f"getConfig failed: {result}")

        raw_io = result.get("ioData", "{}")
        if isinstance(raw_io, str):
            raw_io = json.loads(raw_io)

        state: dict = {}
        for item in raw_io.get("ids", []):
            state.update(item)

        return {
            "target_temp": state.get("targetTemp", 0) / TEMP_SCALE,
            "current_temp": state.get("temperature", 0) / TEMP_SCALE,
            "thermostat_mode": state.get("thermostatMode", 0),
            "humidity": state.get("humidity"),
            "rssi": state.get("rssi"),
            "output": state.get("output"),  # 1 = heating active
            "away_temp": state.get("tAway", 0) / TEMP_SCALE,
            "locked": bool(state.get("lock")),
            "firmware": state.get("vs"),
        }

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------

    def _set_config(self, device_id: str, payload: dict) -> None:
        """Send a setConfig command."""
        self.ensure_authenticated()
        body = {
            "deviceId": device_id,
            "timeOut": COMMAND_TIMEOUT,
            "data": {
                "cmd": "setConfig",
                "rid": 0,
                "ids": [payload],
            },
        }
        result = _request(
            IOT_COMMAND_URL,
            method="POST",
            headers=self._common_headers(auth_token=self._auth_token_header()),
            body=body,
        )
        inner = result.get("ioData", "{}")
        if isinstance(inner, str):
            inner = json.loads(inner)
        if inner.get("status") != 200:
            raise ZentralyConnectionError(f"setConfig failed: {result}")

    def set_temperature(self, device_id: str, temperature: float) -> None:
        """Set target temperature (in °C)."""
        centidegrees = round(temperature * TEMP_SCALE)
        _LOGGER.debug("set_temperature %s → %d centidegrees", device_id, centidegrees)
        self._set_config(device_id, {"targetTemp": centidegrees})

    def set_hvac_mode(self, device_id: str, mode: int) -> None:
        """Set thermostatMode (0=off, 4=manual/heat, etc.)."""
        _LOGGER.debug("set_hvac_mode %s → mode %d", device_id, mode)
        self._set_config(device_id, {"thermostatMode": mode})
