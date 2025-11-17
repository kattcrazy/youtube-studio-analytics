"""Sensor entities for YouTube Studio Analytics integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, METRICS_30D, METRICS_LIFETIME
from .coordinator import YouTubeAnalyticsDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Metric name to friendly name mapping
METRIC_FRIENDLY_NAMES = {
    # 30-day metrics
    "views": "Views",
    "estimatedMinutesWatched": "Watch Hours",
    "averageViewDuration": "Average View Duration",
    "averageViewPercentage": "Average View Percentage",
    "likes": "Likes",
    "dislikes": "Dislikes",
    "comments": "Comments",
    "shares": "Shares",
    "subscribersGained": "Subscribers Gained",
    "subscribersLost": "Subscribers Lost",
    "annotationClicks": "Annotation Clicks",
    "annotationClickThroughRate": "Annotation Click Through Rate",
    "annotationClosableImpressions": "Annotation Closable Impressions",
    # Lifetime metrics
    "subscriber_count": "Subscriber Count",
    "video_count": "Video Count",
    "view_count": "Total Views",
    "channel_title": "Channel Title",
}

# Metric to unit mapping
METRIC_UNITS = {
    "estimatedMinutesWatched": "h",  # Convert minutes to hours
    "averageViewDuration": "s",
    "averageViewPercentage": "%",
    "annotationClickThroughRate": "%",
}

# Metric to device class mapping
METRIC_DEVICE_CLASSES = {
    "estimatedMinutesWatched": SensorDeviceClass.DURATION,
    "averageViewDuration": SensorDeviceClass.DURATION,
}

# Metric to state class mapping
METRIC_STATE_CLASSES = {
    "views": SensorStateClass.TOTAL_INCREASING,
    "estimatedMinutesWatched": SensorStateClass.TOTAL_INCREASING,
    "averageViewDuration": SensorStateClass.MEASUREMENT,
    "averageViewPercentage": SensorStateClass.MEASUREMENT,
    "likes": SensorStateClass.TOTAL_INCREASING,
    "dislikes": SensorStateClass.TOTAL_INCREASING,
    "comments": SensorStateClass.TOTAL_INCREASING,
    "shares": SensorStateClass.TOTAL_INCREASING,
    "subscribersGained": SensorStateClass.TOTAL_INCREASING,
    "subscribersLost": SensorStateClass.TOTAL_INCREASING,
    "annotationClicks": SensorStateClass.TOTAL_INCREASING,
    "annotationClickThroughRate": SensorStateClass.MEASUREMENT,
    "annotationClosableImpressions": SensorStateClass.TOTAL_INCREASING,
    "subscriber_count": SensorStateClass.MEASUREMENT,
    "video_count": SensorStateClass.TOTAL_INCREASING,
    "view_count": SensorStateClass.TOTAL_INCREASING,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up YouTube Studio Analytics sensor entities."""
    coordinator: YouTubeAnalyticsDataUpdateCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]["coordinator"]
    channel_id = entry.data["channel_id"]
    channel_title = entry.data.get("channel_title", "YouTube Channel")

    entities: list[YouTubeAnalyticsSensor] = []

    # Create sensors for all 30-day metrics
    for metric in METRICS_30D:
        entities.append(
            YouTubeAnalyticsSensor(
                coordinator=coordinator,
                channel_id=channel_id,
                channel_title=channel_title,
                metric_key=metric,
                is_30d=True,
            )
        )

    # Create sensors for all lifetime metrics
    for metric in METRICS_LIFETIME:
        entities.append(
            YouTubeAnalyticsSensor(
                coordinator=coordinator,
                channel_id=channel_id,
                channel_title=channel_title,
                metric_key=metric,
                is_30d=False,
            )
        )

    async_add_entities(entities)


class YouTubeAnalyticsSensor(
    CoordinatorEntity[YouTubeAnalyticsDataUpdateCoordinator], SensorEntity
):
    """Representation of a YouTube Studio Analytics sensor."""

    def __init__(
        self,
        coordinator: YouTubeAnalyticsDataUpdateCoordinator,
        channel_id: str,
        channel_title: str,
        metric_key: str,
        is_30d: bool,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._channel_id = channel_id
        self._channel_title = channel_title
        self._metric_key = metric_key
        self._is_30d = is_30d

        # Build entity name and unique_id
        friendly_name = METRIC_FRIENDLY_NAMES.get(metric_key, metric_key)
        if is_30d:
            self._attr_name = f"{channel_title} {friendly_name} (30 days)"
            self._attr_unique_id = f"{channel_id}_{metric_key}_30d"
        else:
            self._attr_name = f"{channel_title} {friendly_name}"
            self._attr_unique_id = f"{channel_id}_{metric_key}"

        # Set device class, unit, and state class
        self._attr_device_class = METRIC_DEVICE_CLASSES.get(metric_key)
        self._attr_native_unit_of_measurement = METRIC_UNITS.get(metric_key)
        self._attr_state_class = METRIC_STATE_CLASSES.get(metric_key)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._channel_id)},
            name=self._channel_title,
            manufacturer="YouTube",
            model="YouTube Channel",
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    @property
    def native_value(self) -> StateType:
        """Return the native value of the sensor."""
        if not self.coordinator.data:
            return None

        data = self.coordinator.data

        # Get value from data
        value = data.get(self._metric_key)

        # Handle special cases
        if self._metric_key == "estimatedMinutesWatched" and value is not None:
            # Convert minutes to hours
            value = round(value / 60, 2)

        # Convert channel_title to string if it's the metric
        if self._metric_key == "channel_title":
            return str(value) if value else None

        # Return None for missing values, otherwise return the value
        return value if value is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs: dict[str, Any] = {
            "channel_id": self._channel_id,
            "channel_name": self._channel_title,
        }

        if self.coordinator.data:
            data = self.coordinator.data

            # Add last_updated timestamp
            if "last_updated" in data:
                attrs["last_updated"] = data["last_updated"]

            # Add date range for 30-day metrics
            if self._is_30d:
                attrs["date_range"] = "30 days"

        return attrs
