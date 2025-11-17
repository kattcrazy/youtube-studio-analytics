"""YouTube API client for YouTube Studio Analytics integration."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError
from homeassistant.core import HomeAssistant

from .const import (
    ANALYTICS_DATE_RANGE_30D,
    OAUTH_SCOPES,
    OAUTH_TOKEN_URL,
    YOUTUBE_ANALYTICS_API_VERSION,
    YOUTUBE_DATA_API_VERSION,
)


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

    async def _get_credentials(self) -> Credentials:
        """Get or refresh credentials.

        Always creates fresh credentials and refreshes to ensure brand channel support.
        Follows the pattern: create Credentials with None token, then refresh to get valid token.

        Raises:
            RefreshError: If token refresh fails (e.g., refresh token expired).
        """
        creds = Credentials(
            token=None,
            refresh_token=self._refresh_token,
            token_uri=OAUTH_TOKEN_URL,
            client_id=self._client_id,
            client_secret=self._client_secret,
            scopes=OAUTH_SCOPES,
        )

        await self.hass.async_add_executor_job(creds.refresh, Request())

        return creds

    async def _get_analytics_service(self) -> Any:
        """Get YouTube Analytics API service.

        Always builds a fresh service with refreshed credentials to ensure brand channel support.

        Raises:
            RefreshError: If token refresh fails (e.g., refresh token expired).
        """
        from googleapiclient.discovery import build

        credentials = await self._get_credentials()
        service = await self.hass.async_add_executor_job(
            build,
            "youtubeAnalytics",
            YOUTUBE_ANALYTICS_API_VERSION,
            credentials=credentials,
        )
        return service

    async def _get_data_service(self) -> Any:
        """Get YouTube Data API v3 service.

        Always builds a fresh service with refreshed credentials to ensure brand channel support.

        Raises:
            RefreshError: If token refresh fails (e.g., refresh token expired).
        """
        from googleapiclient.discovery import build

        credentials = await self._get_credentials()
        service = await self.hass.async_add_executor_job(
            build,
            "youtube",
            YOUTUBE_DATA_API_VERSION,
            credentials=credentials,
        )
        return service

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
            if response.get("items"):
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
            return {"error": "Channel not found"}
        except RefreshError as err:
            return {"error": "auth_failed", "error_detail": str(err)}
        except HttpError as err:
            status_code = getattr(err.resp, "status", "unknown") if hasattr(err, "resp") else "unknown"
            if status_code == 401:
                return {"error": "auth_failed", "error_detail": str(err)}
            if status_code == 500:
                return {"error": "server_error_500", "error_detail": str(err)}
            return {"error": f"http_error_{status_code}", "error_detail": str(err)}
        except Exception as err:
            return {"error": str(err)}

    async def async_get_analytics_metrics(
        self, metrics_list: list[str], days: int = ANALYTICS_DATE_RANGE_30D
    ) -> dict[str, Any]:
        """Fetch specified metrics from YouTube Analytics API."""
        try:
            service = await self._get_analytics_service()
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            response = await self.hass.async_add_executor_job(
                service.reports().query(
                    ids=f"channel=={self.channel_id}",
                    startDate=start_date.strftime("%Y-%m-%d"),
                    endDate=end_date.strftime("%Y-%m-%d"),
                    metrics=",".join(metrics_list),
                    dimensions="",
                ).execute
            )
            if response.get("rows"):
                data = response["rows"][0]
                return {
                    header.get("name", f"metric_{i}"): data[i] if i < len(data) else None
                    for i, header in enumerate(response.get("columnHeaders", []))
                }
            return {"error": "No data returned from YouTube Analytics"}
        except RefreshError as err:
            return {"error": "auth_failed", "error_detail": str(err)}
        except HttpError as err:
            status_code = getattr(err.resp, "status", "unknown") if hasattr(err, "resp") else "unknown"
            if status_code == 401:
                return {"error": "auth_failed", "error_detail": str(err)}
            if status_code == 500:
                return {"error": "server_error_500", "error_detail": str(err)}
            return {"error": f"http_error_{status_code}", "error_detail": str(err)}
        except Exception as err:
            return {"error": str(err)}

    async def async_get_recent_videos_stats(self) -> dict[str, Any]:
        """Fetch statistics for the last 10 videos."""
        default = {
            "recent_videos_count_10vids": 0,
            "recent_videos_total_views_10vids": 0,
            "recent_videos_total_likes_10vids": 0,
            "recent_videos_total_comments_10vids": 0,
        }
        try:
            service = await self._get_data_service()
            videos_response = await self.hass.async_add_executor_job(
                service.search().list(
                    part="snippet",
                    channelId=self.channel_id,
                    type="video",
                    order="date",
                    maxResults=10,
                ).execute
            )
            if not videos_response.get("items"):
                return default
            video_ids = [item["id"]["videoId"] for item in videos_response["items"]]
            videos_stats = await self.hass.async_add_executor_job(
                service.videos().list(part="statistics", id=",".join(video_ids)).execute
            )
            if not videos_stats.get("items"):
                return default
            items = videos_stats["items"]
            return {
                "recent_videos_count_10vids": len(items),
                "recent_videos_total_views_10vids": sum(
                    int(v.get("statistics", {}).get("viewCount", 0)) for v in items
                ),
                "recent_videos_total_likes_10vids": sum(
                    int(v.get("statistics", {}).get("likeCount", 0)) for v in items
                ),
                "recent_videos_total_comments_10vids": sum(
                    int(v.get("statistics", {}).get("commentCount", 0)) for v in items
                ),
            }
        except RefreshError as err:
            return {"error": "auth_failed", "error_detail": str(err)}
        except HttpError as err:
            status_code = getattr(err.resp, "status", "unknown") if hasattr(err, "resp") else "unknown"
            return {"error": f"http_error_{status_code}", "error_detail": str(err)}
        except Exception as err:
            return {"error": str(err)}

    async def async_get_all_metrics(self) -> dict[str, Any]:
        """Fetch all available metrics (30-day analytics, lifetime statistics, and recent videos)."""
        result: dict[str, Any] = {}
        metrics_30d = [
            "views", "averageViewDuration", "averageViewPercentage", "likes", "dislikes",
            "comments", "shares", "subscribersGained", "subscribersLost",
            "annotationClicks", "annotationClickThroughRate", "estimatedMinutesWatched",
            ]
        analytics_30d = await self.async_get_analytics_metrics(metrics_30d, days=ANALYTICS_DATE_RANGE_30D)
        if "error" in analytics_30d:
            result["error_30d"] = analytics_30d["error"]
        else:
            result.update({f"{k}_30d": v for k, v in analytics_30d.items() if k != "error"})
        channel_stats = await self.async_get_channel_statistics()
        if "error" in channel_stats:
            result["error_lifetime"] = channel_stats["error"]
        else:
            result.update({
                "subscriber_count_lifetime": channel_stats.get("subscriber_count", 0),
                "video_count_lifetime": channel_stats.get("video_count", 0),
                "view_count_lifetime": channel_stats.get("view_count", 0),
            })
        recent_videos = await self.async_get_recent_videos_stats()
        if "error" in recent_videos:
            result["error_10vids"] = recent_videos["error"]
        else:
            result.update(recent_videos)
        result["last_updated"] = datetime.now().isoformat()
        return result
