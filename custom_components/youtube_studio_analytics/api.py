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
        _LOGGER.debug("YouTubeAnalyticsAPI.__init__: Initializing API client for channel %s", channel_id)
        self.hass = hass
        self.channel_id = channel_id
        self._refresh_token = refresh_token
        self._client_id = client_id
        self._client_secret = client_secret
        _LOGGER.debug("YouTubeAnalyticsAPI.__init__: API client initialized")

    async def _get_credentials(self) -> Credentials:
        """Get or refresh credentials.
        
        Always creates fresh credentials and refreshes to ensure brand channel support.
        Follows the pattern: create Credentials with None token, then refresh to get valid token.
        
        Raises:
            RefreshError: If token refresh fails (e.g., refresh token expired).
        """
        _LOGGER.debug("_get_credentials: Creating fresh Credentials object with refresh token")
        # Always create credentials with None token (like the example pattern)
        # This ensures we always refresh and get a valid token for the selected channel
        creds = Credentials(
            token=None,  # Always None - we'll refresh to get a fresh token
            refresh_token=self._refresh_token,
            token_uri=OAUTH_TOKEN_URL,
            client_id=self._client_id,
            client_secret=self._client_secret,
            scopes=OAUTH_SCOPES,
        )
        
        _LOGGER.debug("_get_credentials: Refreshing credentials to get valid access token")
        try:
            # Always refresh to get a valid access token
            # This is critical for brand channel support - ensures token matches selected channel
            await self.hass.async_add_executor_job(creds.refresh, Request())
            _LOGGER.debug("_get_credentials: Token refreshed successfully")
        except RefreshError as err:
            _LOGGER.error(
                "_get_credentials: Failed to refresh access token. Refresh token may have expired: %s", err
            )
            raise
        
        return creds

    async def _get_analytics_service(self) -> Any:
        """Get YouTube Analytics API service.
        
        Always builds a fresh service with refreshed credentials to ensure brand channel support.
        
        Raises:
            RefreshError: If token refresh fails (e.g., refresh token expired).
        """
        _LOGGER.debug("_get_analytics_service: Building analytics service with fresh credentials")
        # Import build inside function to avoid blocking import
        from googleapiclient.discovery import build
        
        # Always get fresh credentials (they're refreshed in _get_credentials)
        # This ensures we have the correct token for the selected channel
        credentials = await self._get_credentials()
        service = await self.hass.async_add_executor_job(
            build,
            "youtubeAnalytics",
            YOUTUBE_ANALYTICS_API_VERSION,
            credentials=credentials,
        )
        _LOGGER.debug("_get_analytics_service: Analytics service built successfully")
        return service

    async def _get_data_service(self) -> Any:
        """Get YouTube Data API v3 service.
        
        Always builds a fresh service with refreshed credentials to ensure brand channel support.
        
        Raises:
            RefreshError: If token refresh fails (e.g., refresh token expired).
        """
        _LOGGER.debug("_get_data_service: Building data service with fresh credentials")
        # Import build inside function to avoid blocking import
        from googleapiclient.discovery import build
        
        # Always get fresh credentials (they're refreshed in _get_credentials)
        # This ensures we have the correct token for the selected channel
        credentials = await self._get_credentials()
        service = await self.hass.async_add_executor_job(
            build,
            "youtube",
            YOUTUBE_DATA_API_VERSION,
            credentials=credentials,
        )
        _LOGGER.debug("_get_data_service: Data service built successfully")
        return service

    async def async_get_channel_statistics(self) -> dict[str, Any]:
        """Fetch channel statistics from YouTube Data API v3."""
        _LOGGER.debug("async_get_channel_statistics: Starting fetch for channel %s", self.channel_id)
        try:
            service = await self._get_data_service()
            _LOGGER.debug("async_get_channel_statistics: Executing channels().list() request")
            
            response = await self.hass.async_add_executor_job(
                service.channels().list(
                    part="statistics,snippet",
                    id=self.channel_id,
                ).execute
            )
            
            _LOGGER.debug("async_get_channel_statistics: Response received")
            if "items" in response and len(response["items"]) > 0:
                channel = response["items"][0]
                stats = channel.get("statistics", {})
                snippet = channel.get("snippet", {})
                
                result = {
                    "channel_title": snippet.get("title", "Unknown"),
                    "subscriber_count": int(stats.get("subscriberCount", 0)),
                    "video_count": int(stats.get("videoCount", 0)),
                    "view_count": int(stats.get("viewCount", 0)),
                    "hidden_subscriber_count": stats.get("hiddenSubscriberCount", False),
                }
                _LOGGER.debug("async_get_channel_statistics: Successfully parsed channel statistics")
                return result
            else:
                _LOGGER.warning("async_get_channel_statistics: Channel not found: %s", self.channel_id)
                return {"error": "Channel not found"}
                
        except RefreshError as err:
            _LOGGER.error("async_get_channel_statistics: Authentication failed - refresh token expired: %s", err)
            return {"error": "auth_failed", "error_detail": str(err)}
        except HttpError as err:
            if err.resp.status == 401:
                _LOGGER.error("async_get_channel_statistics: Authentication failed - unauthorized: %s", err)
                return {"error": "auth_failed", "error_detail": str(err)}
            _LOGGER.exception("async_get_channel_statistics: HTTP error fetching channel statistics: %s", err)
            return {"error": str(err)}
        except Exception as err:
            _LOGGER.exception("async_get_channel_statistics: Error fetching channel statistics: %s", err)
            return {"error": str(err)}

    async def async_get_analytics_metrics(
        self, metrics_list: list[str], days: int = ANALYTICS_DATE_RANGE_30D
    ) -> dict[str, Any]:
        """Fetch specified metrics from YouTube Analytics API."""
        _LOGGER.debug("async_get_analytics_metrics: Starting fetch for %d metrics over %d days", len(metrics_list), days)
        try:
            service = await self._get_analytics_service()
            
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            metrics_str = ",".join(metrics_list)
            
            _LOGGER.debug("async_get_analytics_metrics: Querying analytics API from %s to %s", start_date, end_date)
            response = await self.hass.async_add_executor_job(
                service.reports().query(
                    ids=f"channel=={self.channel_id}",
                    startDate=start_date.strftime("%Y-%m-%d"),
                    endDate=end_date.strftime("%Y-%m-%d"),
                    metrics=metrics_str,
                    dimensions="",
                ).execute
            )
            
            _LOGGER.debug("async_get_analytics_metrics: Response received")
            result = {}
            if "rows" in response and len(response["rows"]) > 0:
                data = response["rows"][0]
                column_headers = response.get("columnHeaders", [])
                
                _LOGGER.debug("async_get_analytics_metrics: Processing %d metrics", len(column_headers))
                for i, header in enumerate(column_headers):
                    metric_name = header.get("name", f"metric_{i}")
                    value = data[i] if i < len(data) else None
                    result[metric_name] = value
                _LOGGER.debug("async_get_analytics_metrics: Successfully parsed analytics metrics")
            else:
                _LOGGER.warning(
                    "async_get_analytics_metrics: No data returned from YouTube Analytics for channel %s", self.channel_id
                )
                result["error"] = "No data returned from YouTube Analytics"
            
            return result
            
        except RefreshError as err:
            _LOGGER.error("async_get_analytics_metrics: Authentication failed - refresh token expired: %s", err)
            return {"error": "auth_failed", "error_detail": str(err)}
        except HttpError as err:
            if err.resp.status == 401:
                _LOGGER.error("async_get_analytics_metrics: Authentication failed - unauthorized: %s", err)
                return {"error": "auth_failed", "error_detail": str(err)}
            _LOGGER.exception("async_get_analytics_metrics: HTTP error fetching analytics metrics: %s", err)
            return {"error": str(err)}
        except Exception as err:
            _LOGGER.exception("async_get_analytics_metrics: Error fetching analytics metrics: %s", err)
            return {"error": str(err)}

    async def async_get_all_metrics(self) -> dict[str, Any]:
        """Fetch all available metrics (30-day analytics and lifetime statistics)."""
        _LOGGER.debug("async_get_all_metrics: Starting fetch of all metrics")
        result: dict[str, Any] = {}
        
        try:
            _LOGGER.debug("async_get_all_metrics: Fetching 30-day analytics")
            analytics_30d = await self.async_get_analytics_metrics(
                METRICS_30D, days=ANALYTICS_DATE_RANGE_30D
            )
            
            if "error" in analytics_30d:
                _LOGGER.warning("async_get_all_metrics: Error fetching 30-day analytics: %s", analytics_30d["error"])
                result["error_30d"] = analytics_30d["error"]
            else:
                _LOGGER.debug("async_get_all_metrics: Successfully fetched 30-day analytics")
                for key, value in analytics_30d.items():
                    if key != "error":
                        result[key] = value
            
            _LOGGER.debug("async_get_all_metrics: Fetching channel statistics")
            channel_stats = await self.async_get_channel_statistics()
            
            if "error" in channel_stats:
                _LOGGER.warning("async_get_all_metrics: Error fetching channel statistics: %s", channel_stats["error"])
                result["error_lifetime"] = channel_stats["error"]
            else:
                _LOGGER.debug("async_get_all_metrics: Successfully fetched channel statistics")
                result["subscriber_count"] = channel_stats.get("subscriber_count", 0)
                result["video_count"] = channel_stats.get("video_count", 0)
                result["view_count"] = channel_stats.get("view_count", 0)
                result["channel_title"] = channel_stats.get("channel_title", "Unknown")
            
            result["last_updated"] = datetime.now().isoformat()
            _LOGGER.debug("async_get_all_metrics: Completed successfully")
            
        except Exception as err:
            _LOGGER.exception("async_get_all_metrics: Error fetching all metrics: %s", err)
            result["error"] = str(err)
        
        return result
