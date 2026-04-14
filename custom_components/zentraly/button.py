"""Zentraly button entities."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity, ButtonDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_DEVICE_ID, CONF_DEVICE_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ZentralyResetButton(
                api=data["api"],
                coordinator=data["coordinator"],
                device_id=data["device_id"],
                device_name=entry.data.get(CONF_DEVICE_NAME, entry.data[CONF_DEVICE_ID]),
            )
        ]
    )


class ZentralyResetButton(ButtonEntity):
    """Button that sends a reset command to the thermostat.

    Causes the ESP32 to reboot (~30 s offline) and reconnect to Azure IoT Hub
    with a fresh SAS token. Use this to manually recover a disconnected device
    or to pre-empt the 12-hour token expiry.
    """

    _attr_has_entity_name = True
    _attr_name = "Reiniciar termostato"
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_icon = "mdi:restart"

    def __init__(self, api, coordinator, device_id: str, device_name: str) -> None:
        self._api = api
        self._coordinator = coordinator
        self._device_id = device_id
        self._attr_unique_id = f"zentraly_{device_id}_reset"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "name": device_name,
            "manufacturer": "Zentraly",
            "model": "Termostato WiFi",
        }

    async def async_press(self) -> None:
        """Send reset command and refresh coordinator state."""
        _LOGGER.warning("Zentraly %s: manual reset requested via button", self._device_id)
        accepted = await self.hass.async_add_executor_job(
            self._api.reset_device, self._device_id
        )
        _LOGGER.warning(
            "Zentraly %s: manual reset %s",
            self._device_id,
            "accepted — device will be offline ~30 s" if accepted else "not confirmed by backend",
        )
        await self._coordinator.async_request_refresh()
