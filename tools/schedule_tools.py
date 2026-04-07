import os
import pickle
from datetime import datetime, timedelta
from langchain.tools import tool

CREDENTIALS_FILE = "credentials/credentials.json"
TOKEN_FILE = "credentials/token.pickle"
SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _get_calendar_service():
    """Authenticate and return Google Calendar service."""
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    "Google Calendar credentials not found. "
                    "Please download credentials.json from Google Cloud Console "
                    "and place it in the 'credentials/' folder. "
                    "See CLAUDE.md for setup instructions."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)

    return build("calendar", "v3", credentials=creds)


@tool
def list_upcoming_events(days: int = 7) -> str:
    """
    List upcoming Google Calendar events for the next N days.
    Args:
        days: Number of days to look ahead (default 7).
    """
    try:
        service = _get_calendar_service()
        now = datetime.utcnow()
        end = now + timedelta(days=days)
        events_result = service.events().list(
            calendarId="primary",
            timeMin=now.isoformat() + "Z",
            timeMax=end.isoformat() + "Z",
            maxResults=20,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        events = events_result.get("items", [])
        if not events:
            return f"No events in the next {days} days."
        lines = []
        for e in events:
            start = e["start"].get("dateTime", e["start"].get("date", ""))
            start_fmt = start[:16].replace("T", " ") if "T" in start else start
            lines.append(f"• {start_fmt} | {e.get('summary', 'No title')} (ID:{e['id'][:12]})")
        return "\n".join(lines)
    except FileNotFoundError as e:
        return str(e)
    except Exception as e:
        return f"Failed to fetch events: {e}"


@tool
def get_today_schedule() -> str:
    """Get all events scheduled for today from Google Calendar."""
    try:
        service = _get_calendar_service()
        today = datetime.now().date()
        start = datetime(today.year, today.month, today.day).isoformat() + "Z"
        end = datetime(today.year, today.month, today.day, 23, 59, 59).isoformat() + "Z"
        events_result = service.events().list(
            calendarId="primary",
            timeMin=start,
            timeMax=end,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        events = events_result.get("items", [])
        if not events:
            return "No events scheduled for today."
        lines = [f"Today's Schedule ({today}):"]
        for e in events:
            start_time = e["start"].get("dateTime", e["start"].get("date", ""))
            time_fmt = start_time[11:16] if "T" in start_time else "All day"
            lines.append(f"  {time_fmt} | {e.get('summary', 'No title')}")
        return "\n".join(lines)
    except FileNotFoundError as e:
        return str(e)
    except Exception as e:
        return f"Failed to fetch today's schedule: {e}"


@tool
def create_event(title: str, start_datetime: str, end_datetime: str, description: str = "") -> str:
    """
    Create a new event in Google Calendar.
    Args:
        title: Event title.
        start_datetime: Start time in 'YYYY-MM-DD HH:MM' format.
        end_datetime: End time in 'YYYY-MM-DD HH:MM' format.
        description: Optional event description.
    """
    try:
        service = _get_calendar_service()
        # Convert 'YYYY-MM-DD HH:MM' to RFC3339
        start = datetime.strptime(start_datetime, "%Y-%m-%d %H:%M").isoformat()
        end = datetime.strptime(end_datetime, "%Y-%m-%d %H:%M").isoformat()
        event = {
            "summary": title,
            "description": description,
            "start": {"dateTime": start, "timeZone": "Asia/Jakarta"},
            "end": {"dateTime": end, "timeZone": "Asia/Jakarta"},
        }
        created = service.events().insert(calendarId="primary", body=event).execute()
        return f"Event created: \"{title}\" on {start_datetime} (ID:{created['id'][:12]})"
    except FileNotFoundError as e:
        return str(e)
    except Exception as e:
        return f"Failed to create event: {e}"


@tool
def delete_event(event_id: str) -> str:
    """
    Delete an event from Google Calendar by its ID.
    Args:
        event_id: The event ID (from list_upcoming_events).
    """
    try:
        service = _get_calendar_service()
        # Find full event ID by partial match
        events_result = service.events().list(
            calendarId="primary",
            maxResults=50,
            singleEvents=True,
        ).execute()
        events = events_result.get("items", [])
        full_id = None
        for e in events:
            if e["id"].startswith(event_id):
                full_id = e["id"]
                break
        if not full_id:
            return f"Event ID {event_id} not found."
        service.events().delete(calendarId="primary", eventId=full_id).execute()
        return f"Event {event_id} deleted successfully."
    except FileNotFoundError as e:
        return str(e)
    except Exception as e:
        return f"Failed to delete event: {e}"


@tool
def update_event(event_id: str, title: str = "", start_datetime: str = "", end_datetime: str = "") -> str:
    """
    Update an existing Google Calendar event.
    Args:
        event_id: The event ID prefix (from list_upcoming_events).
        title: New title (leave empty to keep current).
        start_datetime: New start in 'YYYY-MM-DD HH:MM' format (leave empty to keep).
        end_datetime: New end in 'YYYY-MM-DD HH:MM' format (leave empty to keep).
    """
    try:
        service = _get_calendar_service()
        events_result = service.events().list(
            calendarId="primary", maxResults=50, singleEvents=True
        ).execute()
        events = events_result.get("items", [])
        target = next((e for e in events if e["id"].startswith(event_id)), None)
        if not target:
            return f"Event ID {event_id} not found."
        if title:
            target["summary"] = title
        if start_datetime:
            target["start"] = {"dateTime": datetime.strptime(start_datetime, "%Y-%m-%d %H:%M").isoformat(), "timeZone": "Asia/Jakarta"}
        if end_datetime:
            target["end"] = {"dateTime": datetime.strptime(end_datetime, "%Y-%m-%d %H:%M").isoformat(), "timeZone": "Asia/Jakarta"}
        service.events().update(calendarId="primary", eventId=target["id"], body=target).execute()
        return f"Event {event_id} updated: \"{target['summary']}\""
    except FileNotFoundError as e:
        return str(e)
    except Exception as e:
        return f"Failed to update event: {e}"


SCHEDULE_TOOLS = [list_upcoming_events, get_today_schedule, create_event, delete_event, update_event]
