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

# YouTube Analytics API Metrics (30-day period)
METRICS_30D = [
    "views",
    "estimatedMinutesWatched",
    "averageViewDuration",
    "averageViewPercentage",
    "likes",
    "dislikes",
    "comments",
    "shares",
    "subscribersGained",
    "subscribersLost",
    "annotationClicks",
    "annotationClickThroughRate",
    "annotationClosableImpressions",
]

# YouTube Data API v3 Metrics (lifetime totals)
METRICS_LIFETIME = [
    "subscriber_count",
    "video_count",
    "view_count",
    "channel_title",
]

