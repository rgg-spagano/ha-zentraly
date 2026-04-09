#!/usr/bin/env python3
"""
Prueba del cliente API de Zentraly sin Home Assistant.
Corre desde la raíz del proyecto:
    python3 test_api.py
"""
import getpass
import importlib.util
import json
import os
import sys

# Importar api.py directamente (sin cargar __init__.py que requiere homeassistant)
_api_path = os.path.join(os.path.dirname(__file__), "custom_components", "zentraly", "api.py")
_const_path = os.path.join(os.path.dirname(__file__), "custom_components", "zentraly", "const.py")

# Cargar const primero (api lo necesita como .const)
_const_spec = importlib.util.spec_from_file_location("custom_components.zentraly.const", _const_path)
_const_mod = importlib.util.module_from_spec(_const_spec)
sys.modules["custom_components.zentraly.const"] = _const_mod
_const_spec.loader.exec_module(_const_mod)

# Cargar api
_api_spec = importlib.util.spec_from_file_location("custom_components.zentraly.api", _api_path)
_api_mod = importlib.util.module_from_spec(_api_spec)
sys.modules["custom_components.zentraly.api"] = _api_mod
_api_spec.loader.exec_module(_api_mod)

ZentralyAPI = _api_mod.ZentralyAPI
ZentralyAuthError = _api_mod.ZentralyAuthError
ZentralyConnectionError = _api_mod.ZentralyConnectionError

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"

def ok(msg):  print(f"  {GREEN}✓{RESET} {msg}")
def fail(msg): print(f"  {RED}✗{RESET} {msg}")
def info(msg): print(f"  {YELLOW}→{RESET} {msg}")


def main():
    print("=" * 55)
    print("  Zentraly – Test del cliente API")
    print("=" * 55)
    print()

    email    = input("Email de tu cuenta Zentraly: ").strip()
    password = getpass.getpass("Contraseña (no se muestra): ")
    print()

    api = ZentralyAPI(email, password)

    # ── 1. Login ──────────────────────────────────────────────
    print("[ 1 ] Login")
    try:
        result = api.login()
        ok(f"Login exitoso")
        info(f"Token (primeros 40 chars): {api._token[:40]}...")
    except ZentralyAuthError as e:
        fail(f"Auth error: {e}")
        sys.exit(1)
    except ZentralyConnectionError as e:
        fail(f"Conexión: {e}")
        sys.exit(1)
    print()

    # ── 2. Dispositivos ───────────────────────────────────────
    print("[ 2 ] Dispositivos")
    try:
        devices = api.get_devices()
        if not devices:
            fail("No se encontraron dispositivos")
            sys.exit(1)
        for d in devices:
            ok(f"{d['name']}  [ID: {d['device_id']}]  conectado={d['connected']}")
    except Exception as e:
        fail(str(e))
        sys.exit(1)
    print()

    device_id = devices[0]["device_id"]

    # ── 3. Estado actual ──────────────────────────────────────
    print(f"[ 3 ] Estado de '{device_id}'")
    try:
        state = api.get_state(device_id)
        ok(f"Temperatura actual:  {state['current_temp']:.1f} °C")
        ok(f"Setpoint:            {state['target_temp']:.1f} °C")
        ok(f"Modo termostato:     {state['thermostat_mode']}  (0=off, 4=manual)")
        ok(f"Humedad:             {state['humidity']} %")
        ok(f"RSSI:                {state['rssi']} dBm")
        ok(f"Salida (caldera on): {bool(state['output'])}")
        ok(f"Firmware:            {state['firmware']}")
    except Exception as e:
        fail(str(e))
        sys.exit(1)
    print()

    # ── 4. set_temperature (sin cambiar el valor real) ────────
    print("[ 4 ] set_temperature (re-aplica el setpoint actual)")
    current_target = state["target_temp"]
    try:
        api.set_temperature(device_id, current_target)
        ok(f"set_temperature({current_target}) → OK (sin cambios en la caldera)")
    except Exception as e:
        fail(str(e))
        sys.exit(1)
    print()

    # ── 5. set_hvac_mode (re-aplica el modo actual) ───────────
    print("[ 5 ] set_hvac_mode (re-aplica el modo actual)")
    current_mode = state["thermostat_mode"]
    try:
        api.set_hvac_mode(device_id, current_mode)
        ok(f"set_hvac_mode({current_mode}) → OK (sin cambios en el modo)")
    except Exception as e:
        fail(str(e))
        sys.exit(1)
    print()

    print("=" * 55)
    print(f"  {GREEN}Todos los tests pasaron.{RESET} La integración está lista.")
    print("=" * 55)


if __name__ == "__main__":
    main()
