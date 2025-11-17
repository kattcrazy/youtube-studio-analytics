# DO NOT USE NOT READY FOR USE YouTube Studio Analytics

Home Assistant integration for displaying YouTube Studio Analytics data as native sensors.

### Supported metrics/entities
#### 30-Day Analytics
- Views (30 days)
- Watch Hours (30 days)
- Average View Duration
- Average View Percentage
- Likes, Dislikes, Comments, Shares
- Subscribers Gained/Lost
- Annotation Metrics

#### Lifetime Statistics
- Subscriber Count
- Video Count
- Total Views
- Channel Title

## Google Cloud Console Setup

**Important**: You must set up your own OAuth 2.0 credentials in Google Cloud Console.

### Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click on the project dropdown at the top of the page
3. Click **"New Project"**
4. Enter a project name (e.g., "YouTube Studio Analytics")
5. Click **"Create"**
6. Wait for the project to be created, then select it from the project dropdown

### Step 2: Enable Required APIs

1. In the Google Cloud Console, go to **"APIs & Services" > "Library"**
2. Search for **"YouTube Data API v3"** and click on it
3. Click **"Enable"** and wait for it to enable
4. Go back to **"APIs & Services" > "Library"**
5. Search for **"YouTube Analytics API"** and click on it
6. Click **"Enable"** and wait for it to enable

### Step 3: Configure OAuth Consent Screen

1. Go to **"APIs & Services" > "OAuth consent screen"**
2. Select **"External"** (unless you have a Google Workspace organization)
3. Click **"Create"**
4. Fill in the required information:
   - **App name**: YouTube Studio Analytics (or your preferred name)
   - **User support email**: Your email address
   - **Developer contact information**: Your email address
5. Click **"Save and Continue"**
6. On the **"Scopes"** page, click **"Add or Remove Scopes"**
7. Search for and add the following scopes:
   - `https://www.googleapis.com/auth/youtube.readonly`
   - `https://www.googleapis.com/auth/yt-analytics.readonly`
8. Click **"Update"** then **"Save and Continue"**
9. On the **"Test users"** page (for personal use, adding yourself as a test user is sufficient), add your Google account email
10. Click **"Save and Continue"** through the remaining pages

### Step 4: Create OAuth 2.0 Credentials

1. Go to **"APIs & Services" > "Credentials"**
2. Click **"+ CREATE CREDENTIALS"** at the top
3. Select **"OAuth client ID"**
4. Select **"Web application"** as the application type
5. Enter a name for your OAuth client (e.g., "Home Assistant YouTube Analytics")
6. Under **"Authorized redirect URIs"**, add the following:
   ```
   https://my.home-assistant.io/redirect/oauth
   ```
   **Important**: 
   - This is the Home Assistant cloud redirect URL that handles OAuth callbacks automatically
   - No need to configure your instance URL - the cloud service routes the callback to your instance
   - This URL must be added exactly as shown above
7. Click **"Create"**
8. A dialog will appear with your **Client ID** and **Client Secret**. **Save these immediately** - you won't be able to see the secret again!

## Installation (HACS)
1. <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=kattcrazy&category=integration&repository=youtube-studio-analytics" target="_blank" rel="noreferrer noopener"><img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open your Home Assistant instance and open a repository inside the Home Assistant Community Store." /></a>
2. Press download and restart Home Assistant.
3. **Add Application Credentials** (see Step 5 above):
   - Go to `Settings > Applications & Services > Application Credentials`
   - Add your OAuth Client ID and Client Secret from Google Cloud Console
4. Go to `Settings > Devices & Integrations > Add Integration` and search for YouTube Studio Analytics.
5. Authenticate with your Google account and select the channel you want to monitor.
6. Configure update interval (optional, default: 1 hour).

## Installation (manual)
1. Download the folder named `youtube_studio_analytics` inside `custom_components`
2. Drag/upload it into your `custom_components` folder inside your Home Assistant configuration folder (for Home Assistant Docker, `custom_components` is inside the folder that holds your `configuration.yaml`).
3. Restart Home Assistant.
4. Add Application Credentials:
   - Go to `Settings > Applications & Services > Application Credentials`
   - Add your OAuth Client ID and Client Secret from Google Cloud Console
5. Go to `Settings > Devices & Integrations > Add Integration` and search for YouTube Studio Analytics.
6. Authenticate with your Google account and select the channel you want to monitor.
7. Configure update interval (optional, default: 1 hour).

### Troubleshooting
**Missing Application Credentials**: Make sure you've added your OAuth credentials in `Settings > Applications & Services > Application Credentials` before setting up the integration.  
**Trouble authenticating**: Make sure you select the correct Google account during OAuth (brand channels require selecting the brand account).  
**Trouble finding channels**: Are you logged into the correct Google account?
**No data appearing**: Check that your channel has analytics data available. Some metrics may take time to populate.  
**Integration not updating**: Check the update interval in the integration options and ensure Home Assistant can reach YouTube's APIs.

## About
Home Assistant integration for YouTube Studio Analytics. Supports both personal and brand channels with automatic data updates.

Support me [here](https://summersketches.com/product/support-me/)
