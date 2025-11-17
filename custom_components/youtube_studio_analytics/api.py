"""YouTube API client for YouTube Studio Analytics integration."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError
from homeassistant.core import HomeAssistant

from .const import (
    ANALYTICS_DATE_RANGE_30D,
    METRICS_30D,
    METRICS_LIFETIME,
    OAUTH_SCOPES,
    OAUTH_TOKEN_URL,
    YOUTUBE_ANALYTICS_API_VERSION,
    YOUTUBE_DATA_API_VERSION,
)

_LOGGER = logging.getLogger(__name__)


class YouTubeAnalyticsAPI:
    """YouTube API client for fetching analytics and channel data."""

    def __init__(
        self,
        hass: HomeAssistant,
        refresh_token: str,
        channel_id: str,
        client_id: str,
        client_secret: str,
        access_token: str | None = None,
        token_expiry: str | None = None,
    ) -> None:
        """Initialize YouTube Analytics API client."""
        self.hass = hass
        self.channel_id = channel_id
        self._refresh_token = refresh_token
        self._client_id = client_id
        self._client_secret = client_secret
        self._access_token = access_token
        self._token_expiry = datetime.fromisoformat(token_expiry) if token_expiry else None
        
        self._analytics_service = None
        self._data_service = None
        self._credentials: Credentials | None = None

    async def _get_credentials(self) -> Credentials:
        """Get or refresh credentials.
        
        Raises:
            RefreshError: If token refresh fails (e.g., refresh token expired).
        """
        if self._credentials is None or self._credentials.expired:
            if self._credentials is None:
                self._credentials = Credentials(
                    token=self._access_token,
                    refresh_token=self._refresh_token,
                    token_uri=OAUTH_TOKEN_URL,
                    client_id=self._client_id,
                    client_secret=self._client_secret,
                    scopes=OAUTH_SCOPES,
                    expiry=self._token_expiry,
                )
            
            if self._credentials.expired or self._credentials.token is None:
                _LOGGER.debug("Refreshing expired or missing access token")
                try:
                    await self.hass.async_add_executor_job(self._credentials.refresh, Request())
                    self._access_token = self._credentials.token
                    self._token_expiry = self._credentials.expiry
                except RefreshError as err:
                    _LOGGER.error(
                        "Failed to refresh access token. Refresh token may have expired: %s", err
                    )
                    raise
        
        return self._credentials

    async def _get_analytics_service(self) -> Any:
        """Get YouTube Analytics API service.
        
        Raises:
            RefreshError: If token refresh fails (e.g., refresh token expired).
        """
        if self._analytics_service is None:
            # Import build inside function to avoid blocking import
            from googleapiclient.discovery import build
            
            credentials = await self._get_credentials()
            self._analytics_service = await self.hass.async_add_executor_job(
                build,
                "youtubeAnalytics",
                YOUTUBE_ANALYTICS_API_VERSION,
                credentials=credentials,
            )
        return self._analytics_service

    async def _get_data_service(self) -> Any:
        """Get YouTube Data API v3 service.
        
        Raises:
            RefreshError: If token refresh fails (e.g., refresh token expired).
        """
        if self._data_service is None:
            # Import build inside function to avoid blocking import
            from googleapiclient.discovery import build
            
            credentials = await self._get_credentials()
            self._data_service = await self.hass.async_add_executor_job(
                build,
                "youtube",
                YOUTUBE_DATA_API_VERSION,
                credentials=credentials,
            )
        return self._data_service

    async def async_get_channel_statistics(self) -> dict[str, Any]:
        """Fetch channel statistics from YouTube Data API v3."""
        try:
            service = await self._get_data_service()
            
            response = await self.hass.async_add_executor_job(
                service.channels().list(
                    part="statistics,snippet",
                    id=self.channel_id,
                ).execute
            )
            
            if "items" in response and len(response["items"]) > 0:
                channel = response["items"][0]
                stats = channel.get("statistics", {})
                snippet = channel.get("snippet", {})
                
                return {
                    "channel_title": snippet.get("title", "Unknown"),
                    "subscriber_count": int(stats.get("subscriberCount", 0)),
                    "video_count": int(stats.get("videoCount", 0)),
                    "view_count": int(stats.get("viewCount", 0)),
                    "hidden_subscriber_count": stats.get("hiddenSubscriberCount", False),
                }
            else:
                _LOGGER.warning("Channel not found: %s", self.channel_id)
                return {"error": "Channel not found"}
                
        except RefreshError as err:
            _LOGGER.error("Authentication failed - refresh token expired: %s", err)
            return {"error": "auth_failed", "error_detail": str(err)}
        except HttpError as err:
            if err.resp.status == 401:
                _LOGGER.error("Authentication failed - unauthorized: %s", err)
                return {"error": "auth_failed", "error_detail": str(err)}
            _LOGGER.exception("HTTP error fetching channel statistics: %s", err)
            return {"error": str(err)}
        except Exception as err:
            _LOGGER.exception("Error fetching channel statistics: %s", err)
            return {"error": str(err)}

    async def async_get_analytics_metrics(
        self, metrics_list: list[str], days: int = ANALYTICS_DATE_RANGE_30D
    ) -> dict[str, Any]:
        """Fetch specified metrics from YouTube Analytics API."""
        try:
            service = await self._get_analytics_service()
            
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            
            metrics_str = ",".join(metrics_list)
            
            response = await self.hass.async_add_executor_job(
                service.reports().query(
                    ids=f"channel=={self.channel_id}",
                    startDate=start_date.strftime("%Y-%m-%d"),
                    endDate=end_date.strftime("%Y-%m-%d"),
                    metrics=metrics_str,
                    dimensions="",
                ).execute
            )
            
            result = {}
            if "rows" in response and len(response["rows"]) > 0:
                data = response["rows"][0]
                column_headers = response.get("columnHeaders", [])
                
                for i, header in enumerate(column_headers):
                    metric_name = header.get("name", f"metric_{i}")
                    value = data[i] if i < len(data) else None
                    result[metric_name] = value
            else:
                _LOGGER.warning(
                    "No data returned from YouTube Analytics for channel %s", self.channel_id
                )
                result["error"] = "No data returned from YouTube Analytics"
            
            return result
            
        except RefreshError as err:
            _LOGGER.error("Authentication failed - refresh token expired: %s", err)
            return {"error": "auth_failed", "error_detail": str(err)}
        except HttpError as err:
            if err.resp.status == 401:
                _LOGGER.error("Authentication failed - unauthorized: %s", err)
                return {"error": "auth_failed", "error_detail": str(err)}
            _LOGGER.exception("HTTP error fetching analytics metrics: %s", err)
            return {"error": str(err)}
        except Exception as err:
            _LOGGER.exception("Error fetching analytics metrics: %s", err)
            return {"error": str(err)}

    async def async_get_all_metrics(self) -> dict[str, Any]:
        """Fetch all available metrics (30-day analytics and lifetime statistics)."""
        result: dict[str, Any] = {}
        
        try:
            analytics_30d = await self.async_get_analytics_metrics(
                METRICS_30D, days=ANALYTICS_DATE_RANGE_30D
            )
            
            if "error" in analytics_30d:
                _LOGGER.warning("Error fetching 30-day analytics: %s", analytics_30d["error"])
                result["error_30d"] = analytics_30d["error"]
            else:
                for key, value in analytics_30d.items():
                    if key != "error":
                        result[key] = value
            
            channel_stats = await self.async_get_channel_statistics()
            
            if "error" in channel_stats:
                _LOGGER.warning("Error fetching channel statistics: %s", channel_stats["error"])
                result["error_lifetime"] = channel_stats["error"]
            else:
                result["subscriber_count"] = channel_stats.get("subscriber_count", 0)
                result["video_count"] = channel_stats.get("video_count", 0)
                result["view_count"] = channel_stats.get("view_count", 0)
                result["channel_title"] = channel_stats.get("channel_title", "Unknown")
            
            result["last_updated"] = datetime.now().isoformat()
            
        except Exception as err:
            _LOGGER.exception("Error fetching all metrics: %s", err)
            result["error"] = str(err)
        
        return result
