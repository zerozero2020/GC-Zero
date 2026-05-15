"""
Command handlers for the Telegram calendar bot.

  /add <title>, <date/time> [: <title>, <date/time> ...]   Create one or more events
  /avdg <site> <day>                                        Tag an AVDG workday
  /avdg off <day>                                           Mark a day off
  /edit <title>, <date> > <change>                          Modify an event
  /delete <title>, <date> [: <title>, <date> ...]           Delete one or more events
  /summary                                                  This week's events (detailed)
  /week                                                     Next 7 days
  /today                                                    Today's events
  /suggestions <note>                                       Log a suggestion
  /help                                                     Command list
"""

import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

import dateparser
from dateparser.search import search_dates

import calendar_client

EASTERN = ZoneInfo("America/New_York")
AVDG_RECURRING_ID = "9vs14op0jp88pfl3p2aabrc3o0"
PC_CALENDAR_ID = "8e9431e308160f2a923f3d87d18435553a2d2d461fc67fa05fa5599179f987bb@group.calendar.google.com"
_ALL_CALENDARS = ["primary", PC_CALENDAR_ID]
ADDRESS_BOOK_PATH = os.environ.get("ADDRESS_BOOK_PATH", "../company-addresses.md")

_DS = {
    "PREFER_DATES_FROM": "future",
    "TIMEZONE": "America/New_York",
    "RETURN_AS_TIMEZONE_AWARE": True,
}

COLOR_RULES = [
    (["birthday"], "5"),
    (["avdg"], "9"),
    (["trip", "festival", "rave", "travel", "vacation", "flight"], "7"),
    (["christine"], "4"),
    (["dentist", "doctor", "haircut", "mechanic", "appointment", "physical"], "11"),
]
DEFAULT_COLOR = "10"
_NAME_SKIP = {
    "with", "and", "the", "at", "in", "of", "for", "to", "a", "an",
    "from", "by", "on", "my", "your", "his", "her", "our", "their",
    "time", "day", "off", "work", "event", "tbd", "new", "york",
}
COLOR_NAMES = {"9": "AVDG", "7": "Trip", "4": "Christine", "10": "Friends", "11": "Appt", "5": "Birthday"}
LONG_MEALS = {"lunch", "dinner", "brunch"}

_CATEGORY_MAP = {
    "1": "10", "friends": "10",
    "2": "7",  "trip": "7",
    "3": "11", "appt": "11", "appointment": "11",
    "4": "5",  "birthday": "5",
    "5": "9",  "avdg": "9",
    "6": "4",  "christine": "4",
    "7": "10", "none": "10", "no color": "10", "no": "10",
}
_CATEGORY_PROMPT_LINES = (
    "1. Friends\n2. Trip\n3. Appt\n4. Birthday\n5. AVDG\n6. Christine\n7. No color"
)


@dataclass
class PendingEvent:
    summary: str
    start_time: str
    end_time: str
    recurrence: list = field(default_factory=list)
    calendar_id: str = "primary"

    @property
    def prompt(self) -> str:
        return (
            f"Not sure which category to use for *{self.summary}* — which one?\n"
            + _CATEGORY_PROMPT_LINES
        )


def parse_category_reply(text: str) -> str | None:
    return _CATEGORY_MAP.get(text.strip().lower())


def complete_pending(pending: PendingEvent, color_id: str) -> str:
    kwargs: dict = {
        "summary": pending.summary,
        "start_time": pending.start_time,
        "end_time": pending.end_time,
        "color_id": color_id,
        "calendar_id": pending.calendar_id,
    }
    if pending.recurrence:
        kwargs["recurrence"] = pending.recurrence
    result = calendar_client.create_event(**kwargs)
    start = result["start"]
    if "T" in start:
        dt = datetime.fromisoformat(start).astimezone(EASTERN)
        disp = dt.strftime("%a %b %-d, %-I:%M %p")
    else:
        d = date.fromisoformat(start)
        disp = f"{d.strftime('%a %b %-d')} (all day)"
    category = COLOR_NAMES.get(color_id, "Event")
    return f"Added *{result['summary']}* — {disp} ({category})."

HELP_TEXT = """\
*Calendar Bot Commands*

`/add <title>, <date/time>`
  /add Lunch with Rosie, May 17 noon
  /add Dentist, tomorrow 2pm
  /add Coachella trip, April 11-13
  /add Mom's Birthday, March 15
  _Batch:_ /add Dentist, May 15 2pm : Gym, May 16 7am
  _Project Cook:_ /add [pc] Meeting, June 3 2pm

`/avdg <site> <day>`
  /avdg Hines Monday
  /avdg PAN Tue May 19
  /avdg off Wednesday

`/edit <title>, <date> > <change>`
  /edit dentist, May 15 > 3pm
  /edit lunch Rosie, May 17 > move to 1pm
  /edit dentist, May 15 > location 123 Main St
  _Project Cook:_ /edit [pc] meeting, June 3 > 3pm

`/delete <title>, <date>`
  /delete dentist, May 15
  _Batch:_ /delete dentist, May 15 : gym, May 16
  _Project Cook:_ /delete [pc] meeting, June 3

`/summary` — this week's events with details (all calendars)
`/week`    — next 7 days (all calendars)
`/today`   — today's events (all calendars)

`/suggestions <note>`
  /suggestions add reminder support to events
"""


# ─── helpers ──────────────────────────────────────────────────────────────────

def _parse_calendar_prefix(text: str) -> tuple[str, str]:
    """Strip [pc] prefix and return (calendar_id, cleaned_text)."""
    m = re.match(r'^\[pc\]\s*', text, re.IGNORECASE)
    if m:
        return PC_CALENDAR_ID, text[m.end():]
    return "primary", text


def _list_all_events(time_min=None, time_max=None, query=None) -> list:
    """Fetch and merge events from all calendars, sorted by start time."""
    events = []
    for cal_id in _ALL_CALENDARS:
        events.extend(calendar_client.list_events(time_min=time_min, time_max=time_max, query=query, calendar_id=cal_id))

    def _sort_key(e):
        start = e["start"]
        if "T" in start:
            return datetime.fromisoformat(start).astimezone(EASTERN)
        d = date.fromisoformat(start)
        return datetime(d.year, d.month, d.day, tzinfo=EASTERN)

    return sorted(events, key=_sort_key)


def _has_name(title: str) -> bool:
    words = title.split()
    for word in words[1:]:
        clean = word.strip("'s.,!?-")
        if clean and clean[0].isupper() and clean.lower() not in _NAME_SKIP:
            return True
    return False


def _infer_color(title: str) -> str | None:
    lower = title.lower()
    for keywords, cid in COLOR_RULES:
        if any(k in lower for k in keywords):
            return cid
    if _has_name(title):
        return "10"  # Friends
    return None  # uncertain — caller should ask


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


def _fmt_grouped_events(header: str, events: list) -> str:
    """Format events grouped by day, with each day as a bold heading."""
    from collections import defaultdict
    groups: dict[date, list] = defaultdict(list)
    for e in events:
        start = e["start"]
        if "T" in start:
            d = datetime.fromisoformat(start).astimezone(EASTERN).date()
        else:
            d = date.fromisoformat(start)
        groups[d].append(e)

    lines = [header]
    for d in sorted(groups):
        lines.append(f"\n*{d.strftime('%A, %b %-d')}*")
        for e in groups[d]:
            start = e["start"]
            if "T" in start:
                dt = datetime.fromisoformat(start).astimezone(EASTERN)
                line = f"• {e['summary']} at {dt.strftime('%-I:%M %p')}"
            else:
                line = f"• {e['summary']} — all day"
            if e.get("location"):
                line += f"\n  📍 {e['location']}"
            if e.get("description"):
                line += f"\n  📝 {e['description']}"
            lines.append(line)
    return "\n".join(lines)


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


_DATE_RANGE_RE = re.compile(
    r"\d{1,2}(?:st|nd|rd|th)?\s*[-–]\s*(?:\w+\s+)?\d{1,2}(?:st|nd|rd|th)?",
    re.IGNORECASE,
)


def _has_date_range(text: str) -> bool:
    return bool(_DATE_RANGE_RE.search(text))


def _parse_end_of_range(text: str, start: date) -> date:
    """Return the exclusive end date for a range like 'April 11-13', 'Aug 6th - Aug 9th', or 'May 29 to June 1'."""
    m = re.search(
        r"(\w+)\s+(\d{1,2})(?:st|nd|rd|th)?\s*[-–to]+\s*(?:(\w+)\s+)?(\d{1,2})(?:st|nd|rd|th)?",
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
    events = _list_all_events(
        time_min=start.isoformat(),
        time_max=(start + timedelta(days=1)).isoformat(),
    )
    if not events:
        return "Nothing on your calendar today."
    return "*Today:*\n" + "\n".join(_fmt_event(e) for e in events)


def handle_week() -> str:
    now = datetime.now(EASTERN)
    events = _list_all_events(
        time_min=now.isoformat(),
        time_max=(now + timedelta(days=7)).isoformat(),
    )
    if not events:
        return "Nothing on your calendar this week."
    return "*Next 7 days:*\n" + "\n".join(_fmt_event(e) for e in events)


def _week_end_dt(from_dt: datetime) -> datetime:
    """Return start of the Monday following from_dt's week (i.e. exclusive end of Sunday)."""
    days_to_monday = (7 - from_dt.weekday()) % 7 or 7
    base = from_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return base + timedelta(days=days_to_monday)


def handle_summary() -> str:
    now = datetime.now(EASTERN)
    week_end = _week_end_dt(now)
    events = _list_all_events(
        time_min=now.isoformat(),
        time_max=week_end.isoformat(),
    )
    if not events:
        return "Nothing left on your calendar this week."
    return _fmt_grouped_events("*This week:*", events)


def handle_weekly_preview() -> str:
    now = datetime.now(EASTERN)
    next_monday = _week_end_dt(now)
    next_next_monday = next_monday + timedelta(days=7)
    events = _list_all_events(
        time_min=next_monday.isoformat(),
        time_max=next_next_monday.isoformat(),
    )
    if not events:
        return "Nothing on your calendar next week."
    return _fmt_grouped_events("*Upcoming week:*", events)


# ─── /add ─────────────────────────────────────────────────────────────────────

def _add_one(title: str, date_text: str, calendar_id: str = "primary") -> str | PendingEvent:
    """Add a single event. Returns a confirmation string or PendingEvent if color is unknown."""
    found = search_dates(date_text, settings=_DS, languages=["en"]) if date_text else None

    # No date detected → all-day TBD today using default color
    if not found:
        today = date.today()
        result = calendar_client.create_event(
            summary=title + " (Time TBD)",
            start_time=today.isoformat(),
            end_time=(today + timedelta(days=1)).isoformat(),
            color_id=_infer_color(title) or DEFAULT_COLOR,
            calendar_id=calendar_id,
        )
        return f"Added *{result['summary']}* — today, all day (no date given)."

    date_str, parsed_dt = found[0]
    color_id = _infer_color(title)
    target_date = parsed_dt.date()

    # Birthday → all-day, yearly recurring (color always certain)
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
            calendar_id=calendar_id,
        )
        return f"Added *{result['summary']}* — {target_date.strftime('%b %-d')}, yearly (Birthday)."

    # Trip or no time → all-day
    if color_id == "7" or not _has_time(date_str):
        end_date = _parse_end_of_range(date_text, target_date) if (color_id == "7" or _has_date_range(date_text)) else target_date + timedelta(days=1)
        if color_id is None:
            return PendingEvent(
                summary=title,
                start_time=target_date.isoformat(),
                end_time=end_date.isoformat(),
                calendar_id=calendar_id,
            )
        result = calendar_client.create_event(
            summary=title,
            start_time=target_date.isoformat(),
            end_time=end_date.isoformat(),
            color_id=color_id,
            calendar_id=calendar_id,
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
    if color_id is None:
        return PendingEvent(
            summary=title,
            start_time=parsed_dt.strftime(f"%Y-%m-%dT%H:%M:%S{offset}"),
            end_time=end_dt.strftime(f"%Y-%m-%dT%H:%M:%S{offset}"),
            calendar_id=calendar_id,
        )
    result = calendar_client.create_event(
        summary=title,
        start_time=parsed_dt.strftime(f"%Y-%m-%dT%H:%M:%S{offset}"),
        end_time=end_dt.strftime(f"%Y-%m-%dT%H:%M:%S{offset}"),
        color_id=color_id,
        calendar_id=calendar_id,
    )
    t_disp = f"{parsed_dt.strftime('%-I:%M %p')}–{end_dt.strftime('%-I:%M %p')}"
    return f"Added *{result['summary']}* — {target_date.strftime('%a %b %-d')}, {t_disp} ({COLOR_NAMES.get(color_id, 'Event')})."


def handle_add(text: str) -> str | PendingEvent:
    if not text:
        return "Usage: /add <title>, <date/time>\nExample: /add Lunch with Rosie, May 17 noon"

    calendar_id, text = _parse_calendar_prefix(text)
    entries = [e.strip() for e in text.split(" : ")]

    if len(entries) == 1:
        # Single event — ask for color if unknown
        if "," not in text:
            return "Separate the title and date with a comma.\nExample: /add Dentist, tomorrow 2pm"
        title, date_text = text.split(",", 1)
        return _add_one(title.strip() or "Event", date_text.strip(), calendar_id=calendar_id)

    # Batch — use default color for unknowns, no interactive asking
    results = []
    for entry in entries:
        if "," not in entry:
            results.append(f"⚠️ Skipped '{entry}' — missing comma between title and date.")
            continue
        title, date_text = entry.split(",", 1)
        outcome = _add_one(title.strip() or "Event", date_text.strip(), calendar_id=calendar_id)
        if isinstance(outcome, PendingEvent):
            r = calendar_client.create_event(
                summary=outcome.summary,
                start_time=outcome.start_time,
                end_time=outcome.end_time,
                color_id=DEFAULT_COLOR,
                calendar_id=calendar_id,
                **({"recurrence": outcome.recurrence} if outcome.recurrence else {}),
            )
            results.append(f"Added *{r['summary']}* (category unclear — used default color).")
        else:
            results.append(outcome)
    return "\n".join(results)


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

def _delete_one(entry: str, calendar_id: str = "primary") -> str:
    if "," not in entry:
        return f"⚠️ Skipped '{entry}' — missing comma between title and date."

    query, date_text = entry.split(",", 1)
    query = query.strip()
    date_text = date_text.strip()

    parsed_dt = dateparser.parse(date_text, settings=_DS)
    if not parsed_dt:
        return f"Couldn't parse date '{date_text}'. Try: May 15, tomorrow, Monday."

    target = parsed_dt.date()
    day_start = datetime(target.year, target.month, target.day, tzinfo=EASTERN)
    if _has_date_range(date_text):
        end_date = _parse_end_of_range(date_text, target)
        day_end = datetime(end_date.year, end_date.month, end_date.day, tzinfo=EASTERN)
    else:
        day_end = day_start + timedelta(days=1)

    events = calendar_client.list_events(
        time_min=day_start.isoformat(),
        time_max=day_end.isoformat(),
        query=query or None,
        calendar_id=calendar_id,
    )

    if not events:
        return f"No event matching '{query}' on {target.strftime('%b %-d')}."

    if len(events) > 1 and query:
        narrow = [e for e in events if query.lower() in e["summary"].lower()]
        if narrow:
            events = narrow

    if len(events) > 1:
        lines = [f"Multiple events on {target.strftime('%b %-d')} — be more specific:"]
        lines += [f"• {e['summary']}" for e in events]
        return "\n".join(lines)

    event = events[0]
    calendar_client.delete_event(event["id"], calendar_id=calendar_id)
    return f"Deleted *{event['summary']}* on {target.strftime('%a %b %-d')}."


def handle_delete(text: str) -> str:
    if not text:
        return "Usage: /delete <title>, <date>\nExample: /delete dentist, May 15"

    calendar_id, text = _parse_calendar_prefix(text)
    entries = [e.strip() for e in text.split(" : ")]
    if len(entries) == 1:
        return _delete_one(text, calendar_id=calendar_id)

    return "\n".join(_delete_one(entry, calendar_id=calendar_id) for entry in entries)


# ─── /edit ────────────────────────────────────────────────────────────────────

def handle_edit(text: str) -> str:
    if ">" not in text:
        return (
            "Usage: /edit <title>, <date> > <change>\n"
            "Examples:\n"
            "  /edit dentist, May 15 > 3pm\n"
            "  /edit lunch Rosie, May 17 > move to 1pm\n"
            "  /edit dentist, May 15 > location 123 Main St\n"
            "  /edit dentist, May 15 > title New Name"
        )

    calendar_id, text = _parse_calendar_prefix(text)
    search_part, change_part = text.split(">", 1)
    search_part, change_part = search_part.strip(), change_part.strip()

    if "," not in search_part:
        return "Separate the title and date with a comma.\nExample: /edit dentist, May 15 > 3pm"

    query, date_text = search_part.split(",", 1)
    query = query.strip()
    date_text = date_text.strip()

    parsed_dt = dateparser.parse(date_text, settings=_DS)
    if not parsed_dt:
        return f"Couldn't parse date '{date_text}'. Try: May 15, tomorrow, Monday."

    target = parsed_dt.date()
    day_start = datetime(target.year, target.month, target.day, tzinfo=EASTERN)

    events = calendar_client.list_events(
        time_min=day_start.isoformat(),
        time_max=(day_start + timedelta(days=1)).isoformat(),
        query=query or None,
        calendar_id=calendar_id,
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
        calendar_client.update_event(event_id=event_id, location=loc, calendar_id=calendar_id)
        return f"Updated *{event['summary']}* — location set to {loc}."

    if change_lower.startswith("title ") or change_lower.startswith("rename "):
        new_title = change_part.split(None, 1)[1]
        calendar_client.update_event(event_id=event_id, summary=new_title, calendar_id=calendar_id)
        return f"Renamed to *{new_title}*."

    # New time — parse it and keep the same date + duration
    new_time = dateparser.parse(change_part, settings=_DS)
    if new_time:
        current = calendar_client.get_event(event_id, calendar_id=calendar_id)
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
            calendar_id=calendar_id,
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
