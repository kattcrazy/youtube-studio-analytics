"""Sensor entities for YouTube Studio Analytics integration."""

from __future__ import annotations

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

from .const import DOMAIN, METRICS_30D, METRICS_LIFETIME, METRICS_RECENT_VIDEOS
from .coordinator import YouTubeAnalyticsDataUpdateCoordinator

# Metric name to friendly name mapping (with suffixes)
METRIC_FRIENDLY_NAMES = {
    # 30-day metrics
    "views_30d": "Views",
    "estimatedMinutesWatched_30d": "Watch Hours",
    "averageViewDuration_30d": "Average View Duration",
    "averageViewPercentage_30d": "Average View Percentage",
    "likes_30d": "Likes",
    "dislikes_30d": "Dislikes",
    "comments_30d": "Comments",
    "shares_30d": "Shares",
    "subscribersGained_30d": "Subscribers Gained",
    "subscribersLost_30d": "Subscribers Lost",
    "annotationClicks_30d": "Annotation Clicks",
    "annotationClickThroughRate_30d": "Annotation Click Through Rate",
    # Lifetime metrics
    "subscriber_count_lifetime": "Subscriber Count",
    "video_count_lifetime": "Video Count",
    "view_count_lifetime": "Total Views",
    # Recent videos metrics
    "recent_videos_count_10vids": "Recent Videos Count",
    "recent_videos_total_views_10vids": "Recent Videos Total Views",
    "recent_videos_total_likes_10vids": "Recent Videos Total Likes",
    "recent_videos_total_comments_10vids": "Recent Videos Total Comments",
}

# Metric to unit mapping
METRIC_UNITS = {
    "estimatedMinutesWatched_30d": "h",  # Convert minutes to hours
    "averageViewDuration_30d": "s",
    "averageViewPercentage_30d": "%",
    "annotationClickThroughRate_30d": "%",
}

# Metric to device class mapping
METRIC_DEVICE_CLASSES = {
    "estimatedMinutesWatched_30d": SensorDeviceClass.DURATION,
    "averageViewDuration_30d": SensorDeviceClass.DURATION,
}

# Metric to state class mapping
METRIC_STATE_CLASSES = {
    "views_30d": SensorStateClass.TOTAL_INCREASING,
    "estimatedMinutesWatched_30d": SensorStateClass.TOTAL_INCREASING,
    "averageViewDuration_30d": SensorStateClass.MEASUREMENT,
    "averageViewPercentage_30d": SensorStateClass.MEASUREMENT,
    "likes_30d": SensorStateClass.TOTAL_INCREASING,
    "dislikes_30d": SensorStateClass.TOTAL_INCREASING,
    "comments_30d": SensorStateClass.TOTAL_INCREASING,
    "shares_30d": SensorStateClass.TOTAL_INCREASING,
    "subscribersGained_30d": SensorStateClass.TOTAL_INCREASING,
    "subscribersLost_30d": SensorStateClass.TOTAL_INCREASING,
    "annotationClicks_30d": SensorStateClass.TOTAL_INCREASING,
    "annotationClickThroughRate_30d": SensorStateClass.MEASUREMENT,
    "subscriber_count_lifetime": SensorStateClass.MEASUREMENT,
    "video_count_lifetime": SensorStateClass.TOTAL_INCREASING,
    "view_count_lifetime": SensorStateClass.TOTAL_INCREASING,
    "recent_videos_count_10vids": SensorStateClass.MEASUREMENT,
    "recent_videos_total_views_10vids": SensorStateClass.TOTAL_INCREASING,
    "recent_videos_total_likes_10vids": SensorStateClass.TOTAL_INCREASING,
    "recent_videos_total_comments_10vids": SensorStateClass.TOTAL_INCREASING,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up YouTube Studio Analytics sensor entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    channel_id = entry.data["channel_id"]
    channel_title = entry.data.get("channel_title", "YouTube Channel")
    entities = [
        YouTubeAnalyticsSensor(coordinator, channel_id, channel_title, m, True)
        for m in METRICS_30D
    ] + [
        YouTubeAnalyticsSensor(coordinator, channel_id, channel_title, m, False)
        for m in METRICS_LIFETIME + METRICS_RECENT_VIDEOS
    ]
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

        friendly_name = METRIC_FRIENDLY_NAMES.get(metric_key, metric_key)
        if is_30d:
            self._attr_name = f"{channel_title} {friendly_name} (30 days)"
            self._attr_unique_id = f"{channel_id}_{metric_key}"
        else:
            if "_lifetime" in metric_key:
                self._attr_name = f"{channel_title} {friendly_name} (Lifetime)"
            elif "_10vids" in metric_key:
                self._attr_name = f"{channel_title} {friendly_name} (Last 10 Videos)"
        else:
            self._attr_name = f"{channel_title} {friendly_name}"
            self._attr_unique_id = f"{channel_id}_{metric_key}"

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
        value = self.coordinator.data.get(self._metric_key)
        if self._metric_key == "estimatedMinutesWatched_30d" and value is not None:
            return round(value / 60, 2)
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = {"channel_id": self._channel_id, "channel_name": self._channel_title}
        if self.coordinator.data:
            if "last_updated" in self.coordinator.data:
                attrs["last_updated"] = self.coordinator.data["last_updated"]
            if self._is_30d:
                attrs["date_range"] = "30 days"
            elif "_10vids" in self._metric_key:
                attrs["date_range"] = "Last 10 videos by upload date"
            elif "_lifetime" in self._metric_key:
                attrs["date_range"] = "Lifetime"
        return attrs
