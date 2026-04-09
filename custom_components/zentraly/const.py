"""Constants for the Zentraly integration."""

DOMAIN = "zentraly"

BASE_URL = "https://ztprdrestservicesv2.azurewebsites.net"
LOGIN_URL = f"{BASE_URL}/Login"
APP_URL = f"{BASE_URL}/App"
IOT_COMMAND_URL = f"{BASE_URL}/IOTCommand/Run"

DEFAULT_SCAN_INTERVAL = 30  # seconds
COMMAND_TIMEOUT = 15000  # ms, sent to the thermostat

# thermostatMode values observed via MITM
HVAC_MODE_OFF = 0
HVAC_MODE_HEAT = 1       # calefacción
HVAC_MODE_COOL = 2       # refrigeración
HVAC_MODE_AUTO = 3       # auto / programación
HVAC_MODE_MANUAL = 4     # manual (confirmed via MITM: "Modo manual")
HVAC_MODE_ECO = 5        # eco/away

# Temperature encoding: API uses centidegrees (16.0°C → 1600)
TEMP_SCALE = 100

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_DEVICE_ID = "device_id"
CONF_DEVICE_NAME = "device_name"

ATTR_HUMIDITY = "humidity"
ATTR_RSSI = "rssi"
ATTR_FIRMWARE = "firmware_version"
ATTR_CONNECTED = "connected"
ATTR_OUTPUT = "output"
ATTR_AWAY_TEMP = "away_temperature"
