"""Constants for YouTube Studio Analytics integration."""

DOMAIN = "youtube_studio_analytics"

# OAuth 2.0 Configuration
# IMPORTANT: Replace these with your own OAuth credentials from Google Cloud Console
# See README.md for instructions on how to set up OAuth credentials
OAUTH_CLIENT_ID = "YOUR_CLIENT_ID_HERE.apps.googleusercontent.com"
OAUTH_CLIENT_SECRET = "YOUR_CLIENT_SECRET_HERE"

# OAuth Scopes
OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

# OAuth URLs
OAUTH_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"

# API Endpoints
YOUTUBE_ANALYTICS_API_VERSION = "v2"
YOUTUBE_DATA_API_VERSION = "v3"

# Update Interval (seconds)
DEFAULT_UPDATE_INTERVAL = 3600  # 1 hour

# Date Range (days)
ANALYTICS_DATE_RANGE_30D = 30
ANALYTICS_DATE_RANGE_365D = 365

# YouTube Analytics API Metrics (30-day period) - with _30d suffix
METRICS_30D = [
    "views_30d",
    "averageViewDuration_30d",
    "averageViewPercentage_30d",
    "likes_30d",
    "dislikes_30d",
    "comments_30d",
    "shares_30d",
    "subscribersGained_30d",
    "subscribersLost_30d",
    "annotationClicks_30d",
    "annotationClickThroughRate_30d",
    "estimatedMinutesWatched_30d",  # Watch hours (converted from minutes)
]

# YouTube Data API v3 Metrics (lifetime totals) - with _lifetime suffix
METRICS_LIFETIME = [
    "subscriber_count_lifetime",
    "video_count_lifetime",
    "view_count_lifetime",
]

# Recent videos metrics (last 10 videos) - with _10vids suffix
METRICS_RECENT_VIDEOS = [
    "recent_videos_count_10vids",
    "recent_videos_total_views_10vids",
    "recent_videos_total_likes_10vids",
    "recent_videos_total_comments_10vids",
]