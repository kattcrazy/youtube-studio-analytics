"""Config flow for YouTube Studio Analytics integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.exceptions import HomeAssistantError

from .const import (
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    MAX_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for YouTube Studio Analytics."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options flow."""
        # Import voluptuous inside function to avoid blocking import
        import voluptuous as vol
        
        errors: dict[str, str] = {}

        if user_input is not None:
            update_interval = user_input.get("update_interval")

            if (
                update_interval is not None
                and MIN_UPDATE_INTERVAL
                <= update_interval
                <= MAX_UPDATE_INTERVAL
            ):
                return self.async_create_entry(
                    data={
                        "update_interval": update_interval,
                    }
                )

            errors["base"] = "invalid_interval"

        OPTIONS_SCHEMA = vol.Schema(
            {
                vol.Required(
                    "update_interval",
                    default=DEFAULT_UPDATE_INTERVAL,
                ): vol.All(vol.Coerce(int), vol.Range(min=MIN_UPDATE_INTERVAL, max=MAX_UPDATE_INTERVAL)),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
            errors=errors,
        )


class YouTubeOAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Handle OAuth2 flow for YouTube Studio Analytics."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize OAuth2 flow handler."""
        super().__init__()
        self._channels: list[dict[str, Any]] = []
        self._refresh_token: str | None = None
        self._token: str | None = None
        self._token_expiry: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle initial step - start OAuth flow."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        # Start OAuth2 flow - credentials are managed by application_credentials component
        # The parent class will handle checking for credentials availability
        return await self.async_step_pick_implementation()

    async def async_oauth2_finish(self, result: dict[str, Any]) -> FlowResult:
        """Handle OAuth callback."""
        _LOGGER.debug("OAuth flow finished, processing result")
        try:
            refresh_token = result.get("refresh_token")
            token = result.get("token") or result.get("access_token")
            token_expiry = result.get("token_expiry")
            
            if not refresh_token:
                _LOGGER.debug("No refresh token received from OAuth flow")
                return self.async_abort(reason="oauth_failed")

            try:
                # Import helpers inside function to avoid blocking import
                from .config_flow_helpers import create_credentials_from_oauth_result
                
                credentials, token_expiry_str = await create_credentials_from_oauth_result(
                    self.hass,
                    DOMAIN,
                    token,
                    refresh_token,
                    token_expiry,
                )
            except HomeAssistantError as err:
                _LOGGER.error(
                    "OAuth implementation unavailable: %s", err
                )
                return self.async_abort(reason="oauth_implementation_unavailable")

            # Store tokens temporarily for use in channel selection step
            self._refresh_token = refresh_token
            self._token = token
            self._token_expiry = token_expiry_str

            _LOGGER.debug("Fetching channels (personal and brand)")
            # Import helpers inside function to avoid blocking import
            from .config_flow_helpers import fetch_accessible_channels
            
            self._channels = await fetch_accessible_channels(self.hass, credentials)

            _LOGGER.debug("Found %d accessible channels", len(self._channels))
            if not self._channels:
                _LOGGER.warning("No accessible channels found")
                return self.async_abort(reason="no_channels")

            if len(self._channels) == 1:
                _LOGGER.debug("Only one channel found, auto-selecting: %s", self._channels[0]["title"])
                return await self.async_step_channel_selection(
                    {"channel_id": self._channels[0]["id"]}
                )

            _LOGGER.debug("Multiple channels found, showing selection")
            return await self.async_step_channel_selection()

        except Exception as err:
            _LOGGER.exception("Error finishing OAuth flow: %s", err)
            return self.async_abort(reason="oauth_failed")

    async def async_step_channel_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle channel selection step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            channel_id = user_input.get("channel_id")
            selected_channel = next(
                (ch for ch in self._channels if ch["id"] == channel_id), None
            )

            if selected_channel:
                if not self._refresh_token:
                    _LOGGER.error("Refresh token not available")
                    return self.async_abort(reason="oauth_failed")
                
                # Note: client_id and client_secret are NOT stored in config entry
                # They are retrieved from application_credentials when needed
                return self.async_create_entry(
                    title=f"YouTube: {selected_channel['title']}",
                    data={
                        "refresh_token": self._refresh_token,
                        "token": self._token,
                        "token_expiry": self._token_expiry,
                        "channel_id": channel_id,
                        "channel_title": selected_channel["title"],
                    },
                    options={
                        "update_interval": DEFAULT_UPDATE_INTERVAL,
                    },
                )

            errors["base"] = "channel_not_found"

        if not self._channels:
            return self.async_abort(reason="no_channels")

        # Import voluptuous inside function to avoid blocking import
        import voluptuous as vol

        channel_options = {
            channel["id"]: f"{channel['title']} ({channel['type']})"
            for channel in self._channels
        }

        data_schema = vol.Schema(
            {
                vol.Required("channel_id"): vol.In(channel_options),
            }
        )

        return self.async_show_form(
            step_id="channel_selection",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get options flow handler."""
        return OptionsFlowHandler(config_entry)
