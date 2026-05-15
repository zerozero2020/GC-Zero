import os
import re
from typing import Optional
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build

_HAS_TZ = re.compile(r'(Z|[+-]\d{2}:\d{2})$')

def _rfc3339(time_str: str) -> str:
    """Ensure a datetime string has valid RFC3339 timezone — never double-suffix it."""
    return time_str if _HAS_TZ.search(time_str) else time_str + "Z"


def _get_service():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/calendar"],
    )
    creds.refresh(GoogleRequest())
    return build("calendar", "v3", credentials=creds)


def _time_obj(time_str: str) -> dict:
    """YYYY-MM-DD → date object; YYYY-MM-DDTHH:MM:SS±HH:MM → dateTime object."""
    if "T" in time_str:
        return {"dateTime": time_str, "timeZone": "America/New_York"}
    return {"date": time_str}


def list_events(
    time_min: Optional[str] = None,
    time_max: Optional[str] = None,
    query: Optional[str] = None,
    calendar_id: str = "primary",
) -> list:
    service = _get_service()
    params: dict = {
        "calendarId": calendar_id,
        "singleEvents": True,
        "orderBy": "startTime",
        "maxResults": 20,
    }
    if time_min:
        params["timeMin"] = _rfc3339(time_min)
    if time_max:
        params["timeMax"] = _rfc3339(time_max)
    if query:
        params["q"] = query

    items = service.events().list(**params).execute().get("items", [])
    return [
        {
            "id": e["id"],
            "calendar_id": calendar_id,
            "summary": e.get("summary", "(no title)"),
            "start": e["start"].get("dateTime") or e["start"].get("date"),
            "end": e["end"].get("dateTime") or e["end"].get("date"),
            "location": e.get("location"),
            "description": e.get("description"),
            "colorId": e.get("colorId"),
            "recurrence": e.get("recurrence"),
            "recurringEventId": e.get("recurringEventId"),
        }
        for e in items
    ]


def get_event(event_id: str, calendar_id: str = "primary") -> dict:
    service = _get_service()
    e = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
    return {
        "id": e["id"],
        "calendar_id": calendar_id,
        "summary": e.get("summary", "(no title)"),
        "start": e["start"].get("dateTime") or e["start"].get("date"),
        "end": e["end"].get("dateTime") or e["end"].get("date"),
        "location": e.get("location"),
        "description": e.get("description"),
        "colorId": e.get("colorId"),
        "recurrence": e.get("recurrence"),
        "recurringEventId": e.get("recurringEventId"),
    }


def create_event(
    summary: str,
    start_time: str,
    end_time: str,
    color_id: Optional[str] = None,
    location: Optional[str] = None,
    description: Optional[str] = None,
    recurrence: Optional[list] = None,
    calendar_id: str = "primary",
) -> dict:
    service = _get_service()
    body: dict = {
        "summary": summary,
        "start": _time_obj(start_time),
        "end": _time_obj(end_time),
    }
    if color_id:
        body["colorId"] = color_id
    if location:
        body["location"] = location
    if description:
        body["description"] = description
    if recurrence:
        body["recurrence"] = recurrence

    result = service.events().insert(calendarId=calendar_id, body=body).execute()
    return {"id": result["id"], "summary": result.get("summary"), "htmlLink": result.get("htmlLink")}


def update_event(
    event_id: str,
    summary: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    color_id: Optional[str] = None,
    location: Optional[str] = None,
    description: Optional[str] = None,
    calendar_id: str = "primary",
) -> dict:
    service = _get_service()
    body: dict = {}
    if summary is not None:
        body["summary"] = summary
    if start_time is not None:
        body["start"] = _time_obj(start_time)
    if end_time is not None:
        body["end"] = _time_obj(end_time)
    if color_id is not None:
        body["colorId"] = color_id
    if location is not None:
        body["location"] = location
    if description is not None:
        body["description"] = description

    result = service.events().patch(calendarId=calendar_id, eventId=event_id, body=body).execute()
    return {"id": result["id"], "summary": result.get("summary")}


def delete_event(event_id: str, calendar_id: str = "primary") -> dict:
    service = _get_service()
    service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
    return {"deleted": True, "event_id": event_id}
