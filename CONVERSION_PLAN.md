# YouTube Studio Analytics - Integration Overview

**Status**: ✅ Complete  
**Last Updated**: 2025-01-16
**Home Assistant Version**: 2025.11.2+

## Project Summary

A Home Assistant custom integration that provides native sensors for YouTube Studio Analytics data. The integration uses OAuth 2.0 authentication and supports both personal and brand YouTube channels.

**Key Features:**
- Native HA sensors (not webhooks)
- OAuth 2.0 authentication with brand channel support
- Single channel per integration instance
- Metrics from YouTube Analytics API v2 (30-day) and Data API v3 (lifetime)
- DataUpdateCoordinator with configurable update interval (default 1 hour)
- Channel = Device, Metrics = Sensors

## Architecture

**Data Flow:**

```
YouTube APIs → API Client → Coordinator → Native Sensors → HA UI
```

**Component Structure:**
- **Config Flow** (`config_flow.py`): OAuth2 flow, channel selection, options flow
- **Config Flow Helpers** (`config_flow_helpers.py`): Credential creation and channel fetching utilities
- **Application Credentials** (`application_credentials.py`): Custom OAuth2 implementation for brand channel support
- **API Client** (`api.py`): YouTube API wrapper with token refresh logic
- **Coordinator** (`coordinator.py`): DataUpdateCoordinator for polling and data management
- **Sensors** (`sensor.py`): Entity implementations for all metrics
- **Integration** (`__init__.py`): Setup, device registration, platform forwarding

## File Structure

```
youtube_studio_analytics/
├── custom_components/
│   └── youtube_studio_analytics/
│       ├── __init__.py              # Integration entry point
│       ├── api.py                    # YouTube API client
│       ├── application_credentials.py # OAuth2 implementation
│       ├── config_flow.py            # Config flow handlers
│       ├── config_flow_helpers.py    # Config flow utilities
│       ├── const.py                  # Constants and configuration
│       ├── coordinator.py            # DataUpdateCoordinator
│       ├── manifest.json             # Integration manifest
│       ├── sensor.py                 # Sensor entities
│       └── strings.json              # Translations
└── README.md
```

## Available Metrics

### 30-day Metrics (Analytics API v2)
These metrics include "(30 days)" in the sensor name and "_30d" in the unique_id:
- views
- estimatedMinutesWatched (converted to hours)
- averageViewDuration
- averageViewPercentage
- likes
- dislikes
- comments
- shares
- subscribersGained
- subscribersLost
- annotationClicks
- annotationClickThroughRate
- annotationClosableImpressions

### Lifetime Metrics (Data API v3)
- subscriber_count
- video_count
- view_count
- channel_title

**Note:** Revenue metrics are not available (require monetization + additional permissions).

## OAuth 2.0 Implementation

### Brand Channel Support
The integration uses a custom OAuth2 implementation (`YouTubeOAuth2Implementation`) that extends `AuthImplementation` to support brand channels.

**Critical OAuth Parameters:**

```python
access_type='offline'      # Required for refresh token
prompt='consent'           # CRITICAL: Forces account selection for brand channels
include_granted_scopes='true'
```

### Channel Discovery

The integration discovers channels using:

```python
channels().list(part='snippet', mine=True)           # Personal channels
channels().list(part='snippet', managedByMe=True)    # Brand channels
```

**Important:** Refresh tokens are account-specific. The user selects one channel during setup, and the refresh token is tied to that account.

### Application Credentials
Users provide their own OAuth credentials via Home Assistant's Application Credentials UI:
- Client ID (from Google Cloud Console)
- Client Secret (from Google Cloud Console)
- Redirect URI: `https://my.home-assistant.io/redirect/oauth` (Home Assistant cloud redirect URL)

The integration uses `application_credentials` component for credential management (no hardcoded secrets).

## Configuration Flow

### Setup Process
1. **User Step**: User starts config flow
2. **Pick Implementation**: OAuth2 implementation selection (handled by parent class)
3. **External Auth**: User authorizes on Google's website
4. **OAuth Finish**: Integration receives tokens and fetches channels
5. **Channel Selection**: User selects which channel to monitor (auto-selected if only one)
6. **Create Entry**: Config entry created with tokens and channel info

### Options Flow
Users can configure:
- Update interval (15 minutes to 12 hours, default 1 hour)

**Note:** Channel cannot be changed via options - requires re-authentication.

## Data Update Coordinator

**Implementation Details:**

- Uses `DataUpdateCoordinator` with `config_entry` parameter
- Timeout: 30 seconds (`async_timeout.timeout(30)`)
- `always_update=True` (data changes frequently)
- Proper error handling: `ConfigEntryAuthFailed` for auth errors, `UpdateFailed` for API errors
- Update interval configurable via options flow

**Update Process:**
1. Coordinator polls API at configured interval
2. Fetches all metrics (30-day + lifetime)
3. Pre-processes data into lookup dictionary
4. Notifies all sensor entities via `_handle_coordinator_update`

## Sensor Entities

**Implementation:**

- Extends `CoordinatorEntity[YouTubeAnalyticsDataUpdateCoordinator]` and `SensorEntity`
- Implements `_handle_coordinator_update()` callback
- Uses `async_write_ha_state()` for state updates
- Each sensor linked to device (channel)

**Naming Convention:**
- 30-day metrics: `"{channel_title} {metric_name} (30 days)"`
- Lifetime metrics: `"{channel_title} {metric_name}"`
- Unique IDs: `"{channel_id}_{metric_key}_30d"` or `"{channel_id}_{metric_key}"`

**Special Handling:**

- `estimatedMinutesWatched`: Converted from minutes to hours
- `channel_title`: Returned as string

## Error Handling

### Authentication Errors

- `ConfigEntryAuthFailed`: Raised when refresh token expires
- Triggers reauthentication flow automatically
- User must reconfigure integration

### API Errors

- `UpdateFailed`: Raised for API communication errors
- Coordinator retries on next update interval
- Errors logged but don't stop integration

### OAuth Flow Errors
- `oauth_failed`: General OAuth failure
- `oauth_implementation_unavailable`: Credentials not available
- `no_channels`: No accessible channels found
- `already_configured`: Integration already set up

## Constants & Configuration

**Update Intervals:**

- Default: 3600 seconds (1 hour)
- Minimum: 900 seconds (15 minutes)
- Maximum: 43200 seconds (12 hours)

**OAuth Scopes:**

- `https://www.googleapis.com/auth/youtube.readonly`
- `https://www.googleapis.com/auth/yt-analytics.readonly`

**API Versions:**

- YouTube Analytics API: v2
- YouTube Data API: v3

## Dependencies

**Python Packages:**

- `google-api-python-client>=2.100.0`
- `google-auth-httplib2>=0.1.1`
- `google-auth-oauthlib>=1.1.0`

**Home Assistant Components:**

- `application_credentials` (required)

## Design Decisions

### Why Custom OAuth2 Implementation?
The standard OAuth2 implementation doesn't support the `prompt='consent'` parameter needed for brand channel account selection. The custom implementation allows us to:
- Force account selection during OAuth
- Support both personal and brand channels
- Store OAuth flow state for token exchange

### Why Separate Config Flow Helpers?
The config flow was getting too long (~300 lines). Extracted helper functions:
- `create_credentials_from_oauth_result()`: Credential creation logic
- `fetch_accessible_channels()`: Channel discovery logic

This keeps the config flow focused on flow management and improves maintainability.

### Why Always Update?
Set `always_update=True` because:
- YouTube analytics data changes frequently
- Metrics are time-based (30-day windows shift)
- Users expect real-time updates

### Token Storage
- **Stored in Config Entry**: `refresh_token`, `token`, `token_expiry`, `channel_id`, `channel_title`
- **NOT Stored**: `client_id`, `client_secret` (retrieved from application_credentials when needed)
- **Security**: Credentials never stored in config entry, only retrieved at runtime

## Testing Checklist

When testing or debugging:

- [ ] OAuth flow completes successfully
- [ ] Brand channels appear in selection
- [ ] Channel selection works (single and multiple)
- [ ] Sensors created for all metrics
- [ ] Sensor names include "(30 days)" for 30-day metrics
- [ ] Data updates at configured interval
- [ ] Token refresh works automatically
- [ ] Auth failure triggers reauthentication
- [ ] Options flow updates interval correctly
- [ ] Device registry shows correct channel info

## Common Issues

### "No accessible channels found"
- User may not have granted correct scopes
- Brand channel may require account selection (check `prompt='consent'` is set)
- User may not have any channels

### "OAuth implementation unavailable"
- Application credentials not configured
- Internet connection issue
- Home Assistant URL not configured

### "Authentication failed"
- Refresh token expired (user must reconfigure)
- OAuth credentials revoked in Google Cloud Console
- Scopes changed or insufficient

## Future Enhancements

Potential improvements:
- Support multiple channels per instance
- Add revenue metrics (requires monetization)
- Add video-level analytics
- Support custom date ranges
- Add more granular metrics (hourly/daily breakdowns)

## References

- [Home Assistant Integration Documentation](https://developers.home-assistant.io/docs/creating_integration_manifest/)
- [Data Entry Flow Documentation](https://developers.home-assistant.io/docs/config_entries_config_flow_handler/)
- [Application Credentials Documentation](https://developers.home-assistant.io/docs/auth_application_credentials/)
- [YouTube Analytics API Documentation](https://developers.google.com/youtube/analytics)
- [YouTube Data API Documentation](https://developers.google.com/youtube/v3)
