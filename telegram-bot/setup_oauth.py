"""
One-time script to get your Google OAuth refresh token.

Prerequisites:
1. Go to https://console.cloud.google.com/
2. Create a project (or use an existing one)
3. Enable the Google Calendar API
4. Go to APIs & Services → Credentials → Create Credentials → OAuth client ID
5. Choose "Desktop app", download the JSON, save it as credentials.json in this folder

Then run:
    python setup_oauth.py

A browser window will open — sign in with zerobitches2020@gmail.com and grant access.
The script prints the three values you need for your .env file / Railway env vars.
"""
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar"]

flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
creds = flow.run_local_server(port=0)

print("\n=== Add these to your .env / Railway environment variables ===\n")
print(f"GOOGLE_CLIENT_ID={creds.client_id}")
print(f"GOOGLE_CLIENT_SECRET={creds.client_secret}")
print(f"GOOGLE_REFRESH_TOKEN={creds.refresh_token}")
print("\nDone! You can delete credentials.json — the refresh token is all you need going forward.")
