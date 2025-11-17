"""Data update coordinator for YouTube Studio Analytics integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import async_timeout

from homeassistant.config_entries import ConfigEntry, ConfigEntryAuthFailed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import YouTubeAnalyticsAPI
from .const import DOMAIN


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
            logger=None,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=timedelta(seconds=update_interval),
            always_update=True,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from YouTube Analytics API."""
        async with async_timeout.timeout(30):
            data = await self.api_client.async_get_all_metrics()
            if "error" in data:
                if data.get("error") == "auth_failed":
                    raise ConfigEntryAuthFailed(
                        f"Authentication failed: {data.get('error_detail', 'Refresh token expired')}"
                    )
                raise UpdateFailed(f"Error fetching data: {data.get('error', 'Unknown error')}")
            if not data:
                raise UpdateFailed("No data returned from YouTube Analytics API")
            return data
