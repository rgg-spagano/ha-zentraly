"""Config flow for Zentraly integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .api import ZentralyAPI, ZentralyAuthError, ZentralyConnectionError
from .const import CONF_DEVICE_ID, CONF_DEVICE_NAME, CONF_EMAIL, CONF_PASSWORD, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_and_get_devices(hass: HomeAssistant, data: dict) -> list[dict]:
    """Validate credentials and return list of devices."""
    api = ZentralyAPI(data[CONF_EMAIL], data[CONF_PASSWORD])
    try:
        await hass.async_add_executor_job(api.login)
        devices = await hass.async_add_executor_job(api.get_devices)
    except ZentralyAuthError as exc:
        raise InvalidAuth(str(exc)) from exc
    except ZentralyConnectionError as exc:
        raise CannotConnect(str(exc)) from exc
    return devices


class ZentralyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Zentraly."""

    VERSION = 1

    def __init__(self) -> None:
        self._devices: list[dict] = []
        self._credentials: dict = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step: ask for credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                self._devices = await validate_and_get_devices(self.hass, user_input)
                self._credentials = user_input
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception during Zentraly config flow")
                errors["base"] = "unknown"
            else:
                if len(self._devices) == 1:
                    # Only one device → create entry directly
                    device = self._devices[0]
                    return self.async_create_entry(
                        title=device["name"],
                        data={
                            **self._credentials,
                            CONF_DEVICE_ID: device["device_id"],
                            CONF_DEVICE_NAME: device["name"],
                        },
                    )
                # Multiple devices → let user pick
                return await self.async_step_device()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Let the user select which thermostat to add."""
        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID]
            device = next(d for d in self._devices if d["device_id"] == device_id)
            return self.async_create_entry(
                title=device["name"],
                data={
                    **self._credentials,
                    CONF_DEVICE_ID: device["device_id"],
                    CONF_DEVICE_NAME: device["name"],
                },
            )

        device_options = {d["device_id"]: d["name"] for d in self._devices}
        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema(
                {vol.Required(CONF_DEVICE_ID): vol.In(device_options)}
            ),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
