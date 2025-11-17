"""Data update coordinator for YouTube Studio Analytics integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import async_timeout

from homeassistant.config_entries import ConfigEntry, ConfigEntryAuthFailed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import YouTubeAnalyticsAPI
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class YouTubeAnalyticsDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data from YouTube Analytics API."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api_client: YouTubeAnalyticsAPI,
        update_interval: int,
    ) -> None:
        """Initialize coordinator.

        Args:
            hass: Home Assistant instance.
            config_entry: Config entry for this coordinator.
            api_client: YouTube Analytics API client instance.
            update_interval: Update interval in seconds.
        """
        self.api_client = api_client

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=timedelta(seconds=update_interval),
            always_update=True,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from YouTube Analytics API.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.

        Returns:
            Dictionary containing all metrics from YouTube Analytics API.

        Raises:
            UpdateFailed: If unable to fetch data from API.
            ConfigEntryAuthFailed: If authentication fails (token expired).
        """
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(30):
                data = await self.api_client.async_get_all_metrics()

                if "error" in data:
                    error_msg = data.get("error", "Unknown error")
                    error_detail = data.get("error_detail", "")
                    
                    if error_msg == "auth_failed":
                        _LOGGER.error(
                            "Authentication failed. Refresh token may have expired: %s", error_detail
                        )
                        raise ConfigEntryAuthFailed(
                            f"Authentication failed: {error_detail or 'Refresh token expired'}"
                        )
                    
                    _LOGGER.error("Error fetching YouTube Analytics data: %s", error_msg)
                    raise UpdateFailed(f"Error fetching data: {error_msg}")

                if not data:
                    _LOGGER.warning("No data returned from YouTube Analytics API")
                    raise UpdateFailed("No data returned from YouTube Analytics API")

                _LOGGER.debug("Successfully fetched YouTube Analytics data")
                return data

        except ConfigEntryAuthFailed:
            raise
        except UpdateFailed:
            raise
        except Exception as err:
            _LOGGER.exception("Unexpected error fetching YouTube Analytics data: %s", err)
            raise UpdateFailed(f"Unexpected error: {err}") from err
