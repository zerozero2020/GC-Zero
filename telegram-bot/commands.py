"""
Command handlers for the Telegram calendar bot.

  /add <title> <date/time>           Create a new event
  /avdg <site> <day>                 Tag an AVDG workday
  /avdg off <day>                    Mark a day off (removes AVDG, adds Off Work)
  /edit <title> <date> > <change>    Modify an event
  /delete <title> <date>             Delete an event
  /week                              Next 7 days
  /today                             Today's events
  /suggestions <note>                Log a suggestion for improving the bot
  /help                              Command list
"""

import os
import re
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

import dateparser
from dateparser.search import search_dates

import calendar_client

EASTERN = ZoneInfo("America/New_York")
AVDG_RECURRING_ID = "9vs14op0jp88pfl3p2aabrc3o0"
ADDRESS_BOOK_PATH = os.environ.get("ADDRESS_BOOK_PATH", "../company-addresses.md")

_DS = {
    "PREFER_DATES_FROM": "future",
    "TIMEZONE": "America/New_York",
    "RETURN_AS_TIMEZONE_AWARE": True,
}

COLOR_RULES = [
    (["birthday"], "5"),
    (["avdg"], "9"),
    (["trip", "festival", "rave", "travel", "vacation"], "7"),
    (["christine"], "4"),
    (["dentist", "doctor", "haircut", "mechanic", "appointment", "physical"], "11"),
]
DEFAULT_COLOR = "10"
COLOR_NAMES = {"9": "AVDG", "7": "Trip", "4": "Christine", "10": "Friends", "11": "Appt", "5": "Birthday"}
LONG_MEALS = {"lunch", "dinner", "brunch"}

HELP_TEXT = """\
*Calendar Bot Commands*

`/add <title> <date/time>`
  /add Lunch with Rosie May 17 noon
  /add Dentist tomorrow 2pm
  /add Coachella trip April 11-13
  /add Mom's Birthday March 15

`/avdg <site> <day>`
  /avdg Hines Monday
  /avdg PAN Tue May 19
  /avdg off Wednesday

`/edit <title> <date> > <change>`
  /edit dentist May 15 > 3pm
  /edit lunch Rosie May 17 > move to 1pm
  /edit dentist May 15 > location 123 Main St

`/delete <title> <date>`
  /delete dentist May 15

`/week`   — next 7 days
`/today`  — today's events

`/suggestions <note>`
  /suggestions add reminder support to events
"""


# ─── helpers ──────────────────────────────────────────────────────────────────

def _infer_color(title: str) -> str:
    lower = title.lower()
    for keywords, cid in COLOR_RULES:
        if any(k in lower for k in keywords):
            return cid
    return DEFAULT_COLOR


def _infer_duration(title: str) -> int:
    """Return event duration in minutes."""
    return 120 if any(m in title.lower() for m in LONG_MEALS) else 60


def _offset(dt: datetime) -> str:
    secs = int(dt.utcoffset().total_seconds())
    h, m = divmod(abs(secs) // 60, 60)
    return f"{'+' if secs >= 0 else '-'}{h:02d}:{m:02d}"


_TIME_RE = re.compile(
    r"\b(\d{1,2}(:\d{2})?\s*(am|pm)|noon|midnight|morning|afternoon|evening)\b",
    re.IGNORECASE,
)


def _has_time(text: str) -> bool:
    return bool(_TIME_RE.search(text))


def _fmt_event(e: dict) -> str:
    start = e["start"]
    if "T" in start:
        dt = datetime.fromisoformat(start).astimezone(EASTERN)
        return f"• *{e['summary']}* — {dt.strftime('%a %b %-d, %-I:%M %p')}"
    d = date.fromisoformat(start)
    return f"• *{e['summary']}* — {d.strftime('%a %b %-d')} (all day)"


def _read_address_book() -> str:
    try:
        with open(ADDRESS_BOOK_PATH) as f:
            return f.read()
    except FileNotFoundError:
        return os.environ.get("ADDRESS_BOOK", "")


def _lookup_address(company: str) -> str | None:
    for line in _read_address_book().splitlines():
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if len(cells) >= 2 and cells[0].lower() == company.lower() and cells[1]:
            return cells[1]
    return None


def _parse_end_of_range(text: str, start: date) -> date:
    """Return the exclusive end date for a range like 'April 11-13' or 'May 29 to June 1'."""
    m = re.search(
        r"(\w+)\s+(\d{1,2})\s*[-–to]+\s*(?:(\w+)\s+)?(\d{1,2})",
        text, re.IGNORECASE,
    )
    if m:
        month = m.group(3) or m.group(1)
        end_str = f"{month} {m.group(4)}"
        parsed = dateparser.parse(end_str, settings=_DS)
        if parsed:
            return parsed.date() + timedelta(days=1)  # exclusive
    return start + timedelta(days=1)


# ─── /today and /week ─────────────────────────────────────────────────────────

def handle_today() -> str:
    now = datetime.now(EASTERN)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    events = calendar_client.list_events(
        time_min=start.isoformat(),
        time_max=(start + timedelta(days=1)).isoformat(),
    )
    if not events:
        return "Nothing on your calendar today."
    return "*Today:*\n" + "\n".join(_fmt_event(e) for e in events)


def handle_week() -> str:
    now = datetime.now(EASTERN)
    events = calendar_client.list_events(
        time_min=now.isoformat(),
        time_max=(now + timedelta(days=7)).isoformat(),
    )
    if not events:
        return "Nothing on your calendar this week."
    return "*Next 7 days:*\n" + "\n".join(_fmt_event(e) for e in events)


# ─── /add ─────────────────────────────────────────────────────────────────────

def handle_add(text: str) -> str:
    if not text:
        return "Usage: /add <title> <date/time>\nExample: /add Lunch with Rosie May 17 noon"

    found = search_dates(text, settings=_DS, languages=["en"])

    # No date detected → all-day TBD today
    if not found:
        today = date.today()
        result = calendar_client.create_event(
            summary=text.strip() + " (Time TBD)",
            start_time=today.isoformat(),
            end_time=(today + timedelta(days=1)).isoformat(),
            color_id=_infer_color(text),
        )
        return f"Added *{result['summary']}* — today, all day (no date given)."

    date_str, parsed_dt = found[0]
    title = re.sub(re.escape(date_str), "", text, flags=re.IGNORECASE)
    title = re.sub(r"\s{2,}", " ", title).strip(" ,.-") or "Event"
    color_id = _infer_color(title)
    target_date = parsed_dt.date()

    # Birthday → all-day, yearly recurring
    if color_id == "5":
        if "birthday" not in title.lower():
            name = title.rstrip("'s").rstrip("s")
            title = f"{name}'s Birthday"
        result = calendar_client.create_event(
            summary=title,
            start_time=target_date.isoformat(),
            end_time=(target_date + timedelta(days=1)).isoformat(),
            color_id="5",
            recurrence=["RRULE:FREQ=YEARLY"],
        )
        return f"Added *{result['summary']}* — {target_date.strftime('%b %-d')}, yearly (Birthday)."

    # Trip or no time → all-day
    if color_id == "7" or not _has_time(date_str):
        end_date = _parse_end_of_range(text, target_date) if color_id == "7" else target_date + timedelta(days=1)
        result = calendar_client.create_event(
            summary=title,
            start_time=target_date.isoformat(),
            end_time=end_date.isoformat(),
            color_id=color_id,
        )
        if end_date == target_date + timedelta(days=1):
            d_disp = target_date.strftime("%a %b %-d")
        else:
            d_disp = f"{target_date.strftime('%b %-d')}–{(end_date - timedelta(days=1)).strftime('%b %-d')}"
        suffix = " (Time TBD)" if color_id != "7" else ""
        return f"Added *{result['summary']}* — {d_disp}{suffix} ({COLOR_NAMES.get(color_id, 'Event')})."

    # Timed event
    duration = _infer_duration(title)
    end_dt = parsed_dt + timedelta(minutes=duration)
    offset = _offset(parsed_dt)
    result = calendar_client.create_event(
        summary=title,
        start_time=parsed_dt.strftime(f"%Y-%m-%dT%H:%M:%S{offset}"),
        end_time=end_dt.strftime(f"%Y-%m-%dT%H:%M:%S{offset}"),
        color_id=color_id,
    )
    t_disp = f"{parsed_dt.strftime('%-I:%M %p')}–{end_dt.strftime('%-I:%M %p')}"
    return f"Added *{result['summary']}* — {target_date.strftime('%a %b %-d')}, {t_disp} ({COLOR_NAMES.get(color_id, 'Event')})."


# ─── /avdg ────────────────────────────────────────────────────────────────────

def handle_avdg(text: str) -> str:
    parts = text.strip().split(None, 1)
    if len(parts) < 2:
        return "Usage: /avdg <site> <day>\nExamples:\n  /avdg Hines Monday\n  /avdg off Wednesday"

    site, day_text = parts[0], parts[1]
    parsed = dateparser.parse(day_text, settings=_DS)
    if not parsed:
        return f"Couldn't parse '{day_text}'. Try: Monday, May 19, tomorrow."

    target = parsed.date()
    day_start = datetime(target.year, target.month, target.day, tzinfo=EASTERN)
    day_end = day_start + timedelta(days=1)

    events = calendar_client.list_events(
        time_min=day_start.isoformat(),
        time_max=day_end.isoformat(),
        query="AVDG",
    )
    avdg = next(
        (e for e in events if e.get("recurringEventId") == AVDG_RECURRING_ID),
        None,
    )
    day_disp = target.strftime("%a %b %-d")

    if site.lower() == "off":
        if avdg:
            calendar_client.delete_event(avdg["id"])
        calendar_client.create_event(
            summary="Off Work",
            start_time=target.isoformat(),
            end_time=(target + timedelta(days=1)).isoformat(),
            color_id="9",
        )
        return f"Marked *{day_disp}* as off — AVDG removed, Off Work added."

    if not avdg:
        return f"No AVDG event found on {day_disp}. Is it a weekday?"

    address = _lookup_address(site)
    kwargs: dict = {"event_id": avdg["id"], "summary": f"AVDG ({site})"}
    if address:
        kwargs["location"] = address

    calendar_client.update_event(**kwargs)

    loc = f", 📍 {address}" if address else f" (no address on file for {site})"
    return f"Updated → *AVDG ({site})* on {day_disp}{loc}."


# ─── /delete ──────────────────────────────────────────────────────────────────

def handle_delete(text: str) -> str:
    if not text:
        return "Usage: /delete <title> <date>\nExample: /delete dentist May 15"

    found = search_dates(text, settings=_DS, languages=["en"])
    if not found:
        return "Please include a date. Example: /delete dentist May 15"

    date_str, parsed_dt = found[0]
    query = re.sub(re.escape(date_str), "", text, flags=re.IGNORECASE).strip(" ,.-")
    target = parsed_dt.date()
    day_start = datetime(target.year, target.month, target.day, tzinfo=EASTERN)

    events = calendar_client.list_events(
        time_min=day_start.isoformat(),
        time_max=(day_start + timedelta(days=1)).isoformat(),
        query=query or None,
    )

    if not events:
        return f"No event matching '{query}' on {target.strftime('%b %-d')}."

    # Narrow down if multiple results
    if len(events) > 1 and query:
        narrow = [e for e in events if query.lower() in e["summary"].lower()]
        if narrow:
            events = narrow

    if len(events) > 1:
        lines = [f"Multiple events on {target.strftime('%b %-d')} — be more specific:"]
        lines += [f"• {e['summary']}" for e in events]
        return "\n".join(lines)

    event = events[0]
    calendar_client.delete_event(event["id"])
    return f"Deleted *{event['summary']}* on {target.strftime('%a %b %-d')}."


# ─── /edit ────────────────────────────────────────────────────────────────────

def handle_edit(text: str) -> str:
    if ">" not in text:
        return (
            "Usage: /edit <title> <date> > <change>\n"
            "Examples:\n"
            "  /edit dentist May 15 > 3pm\n"
            "  /edit lunch Rosie May 17 > move to 1pm\n"
            "  /edit dentist May 15 > location 123 Main St\n"
            "  /edit dentist May 15 > title New Name"
        )

    search_part, change_part = text.split(">", 1)
    search_part, change_part = search_part.strip(), change_part.strip()

    found = search_dates(search_part, settings=_DS, languages=["en"])
    if not found:
        return "Include the event date before the >. Example: /edit dentist May 15 > 3pm"

    date_str, parsed_dt = found[0]
    query = re.sub(re.escape(date_str), "", search_part, flags=re.IGNORECASE).strip(" ,.-")
    target = parsed_dt.date()
    day_start = datetime(target.year, target.month, target.day, tzinfo=EASTERN)

    events = calendar_client.list_events(
        time_min=day_start.isoformat(),
        time_max=(day_start + timedelta(days=1)).isoformat(),
        query=query or None,
    )
    if not events:
        return f"No event matching '{query}' on {target.strftime('%b %-d')}."

    if len(events) > 1 and query:
        narrow = [e for e in events if query.lower() in e["summary"].lower()]
        if narrow:
            events = narrow

    if len(events) > 1:
        lines = [f"Multiple matches on {target.strftime('%b %-d')} — be more specific:"]
        lines += [f"• {e['summary']}" for e in events]
        return "\n".join(lines)

    event = events[0]
    event_id = event["id"]
    change_lower = change_part.lower()

    if change_lower.startswith("location "):
        loc = change_part.split(None, 1)[1]
        calendar_client.update_event(event_id=event_id, location=loc)
        return f"Updated *{event['summary']}* — location set to {loc}."

    if change_lower.startswith("title ") or change_lower.startswith("rename "):
        new_title = change_part.split(None, 1)[1]
        calendar_client.update_event(event_id=event_id, summary=new_title)
        return f"Renamed to *{new_title}*."

    # New time — parse it and keep the same date + duration
    new_time = dateparser.parse(change_part, settings=_DS)
    if new_time:
        current = calendar_client.get_event(event_id)
        curr_start = datetime.fromisoformat(current["start"])
        curr_end = datetime.fromisoformat(current["end"])
        duration = curr_end - curr_start

        new_start = curr_start.replace(hour=new_time.hour, minute=new_time.minute, second=0, microsecond=0)
        new_end = new_start + duration
        offset = _offset(new_start)
        calendar_client.update_event(
            event_id=event_id,
            start_time=new_start.strftime(f"%Y-%m-%dT%H:%M:%S{offset}"),
            end_time=new_end.strftime(f"%Y-%m-%dT%H:%M:%S{offset}"),
        )
        t_disp = f"{new_start.strftime('%-I:%M %p')}–{new_end.strftime('%-I:%M %p')}"
        return f"Updated *{event['summary']}* → {t_disp} on {target.strftime('%a %b %-d')}."

    return f"Didn't understand '{change_part}'. Try a time (3pm), 'location <addr>', or 'title <new name>'."


# ─── /suggestions ─────────────────────────────────────────────────────────────

SUGGESTIONS_FILE = os.path.join(os.path.dirname(__file__), "suggestions.md")


def handle_suggestions(text: str) -> str:
    if not text:
        return (
            "Usage: /suggestions <note>\n"
            "Example: /suggestions add reminder support when creating events\n\n"
            "Your note gets saved here and you can paste it into Claude Code to customize the bot."
        )

    timestamp = datetime.now(EASTERN).strftime("%b %-d, %Y %-I:%M %p")
    entry = f"- [{timestamp}] {text}\n"

    with open(SUGGESTIONS_FILE, "a") as f:
        f.write(entry)

    return (
        f"📝 *Suggestion saved:*\n_{text}_\n\n"
        f"Copy and paste the line above into Claude Code to customize the bot."
    )
