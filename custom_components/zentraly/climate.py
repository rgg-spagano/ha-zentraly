"""Zentraly climate entity.

Modos confirmados via MITM:
  thermostatMode 0 → off
  thermostatMode 4 → manual/heat  ("Modo manual" en la app)

Valores adicionales (deducidos por la app, a confirmar):
  thermostatMode 1 → heat automático / schedule
  thermostatMode 2 → cool
  thermostatMode 3 → auto
  thermostatMode 5 → eco/away

Temperatura: API usa centidegrees (21.5°C → 2150).
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_AWAY_TEMP,
    ATTR_CONNECTED,
    ATTR_FIRMWARE,
    ATTR_HUMIDITY,
    ATTR_OUTPUT,
    ATTR_RSSI,
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    DOMAIN,
    HVAC_MODE_MANUAL,
    HVAC_MODE_OFF,
)

_LOGGER = logging.getLogger(__name__)

# Mapping: HA HVACMode → Zentraly thermostatMode value
_HA_TO_ZT: dict[HVACMode, int] = {
    HVACMode.OFF: HVAC_MODE_OFF,
    HVACMode.HEAT: HVAC_MODE_MANUAL,
}

# Mapping: Zentraly thermostatMode → HA HVACMode
_ZT_TO_HA: dict[int, HVACMode] = {v: k for k, v in _HA_TO_ZT.items()}
# Extra modes captured / inferred (will show as HEAT if unknown)
_ZT_TO_HA.update(
    {
        1: HVACMode.HEAT,
        2: HVACMode.COOL,
        3: HVACMode.AUTO,
        5: HVACMode.HEAT,  # eco/away → still heat
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Zentraly climate entity from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ZentralyClimate(
                coordinator=data["coordinator"],
                api=data["api"],
                device_id=data["device_id"],
                device_name=entry.data.get(CONF_DEVICE_NAME, entry.data[CONF_DEVICE_ID]),
                entry_id=entry.entry_id,
            )
        ],
        update_before_add=True,
    )


class ZentralyClimate(CoordinatorEntity, ClimateEntity):
    """Zentraly WiFi thermostat as a HA climate entity."""

    _attr_has_entity_name = True
    _attr_name = None  # uses device name
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_min_temp = 5.0
    _attr_max_temp = 35.0
    _attr_target_temperature_step = 0.5

    def __init__(
        self,
        coordinator,
        api,
        device_id: str,
        device_name: str,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._api = api
        self._device_id = device_id
        self._device_name = device_name
        self._attr_unique_id = f"zentraly_{device_id}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "name": device_name,
            "manufacturer": "Zentraly",
            "model": "Termostato WiFi",
            "sw_version": self._state.get("firmware") if self.coordinator.data else None,
        }

    @property
    def _state(self) -> dict:
        return self.coordinator.data or {}

    @property
    def current_temperature(self) -> float | None:
        return self._state.get("current_temp")

    @property
    def target_temperature(self) -> float | None:
        return self._state.get("target_temp")

    @property
    def hvac_mode(self) -> HVACMode:
        mode_int = self._state.get("thermostat_mode", HVAC_MODE_OFF)
        return _ZT_TO_HA.get(mode_int, HVACMode.OFF)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        if (humidity := self._state.get("humidity")) is not None:
            attrs[ATTR_HUMIDITY] = humidity
        if (rssi := self._state.get("rssi")) is not None:
            attrs[ATTR_RSSI] = rssi
        if (fw := self._state.get("firmware")) is not None:
            attrs[ATTR_FIRMWARE] = fw
        if (output := self._state.get("output")) is not None:
            attrs[ATTR_OUTPUT] = bool(output)
        if (away := self._state.get("away_temp")) is not None:
            attrs[ATTR_AWAY_TEMP] = away
        return attrs

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        await self.hass.async_add_executor_job(
            self._api.set_temperature, self._device_id, temp
        )
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        zt_mode = _HA_TO_ZT.get(hvac_mode)
        if zt_mode is None:
            _LOGGER.warning("Unsupported HVAC mode: %s", hvac_mode)
            return
        await self.hass.async_add_executor_job(
            self._api.set_hvac_mode, self._device_id, zt_mode
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        """Turn on the thermostat (set to manual/heat mode)."""
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        """Turn off the thermostat."""
        await self.async_set_hvac_mode(HVACMode.OFF)
