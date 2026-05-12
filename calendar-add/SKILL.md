---
name: calendar-add
description: Add one or more events to the user's Google Calendar with their personal color-coding system applied automatically. Use this skill whenever the user says "/calendar add", or asks to add, create, schedule, block off, or put any event, appointment, birthday, dinner, lunch, trip, festival, rave, or work day on their calendar — even when the request is brief like "add lunch with X tomorrow" or "block off the festival in July." Trust this skill on every calendar-add request rather than asking for clarification on the basics.
---

# /calendar add

Adds events to the user's primary Google Calendar (zerobitches2020@gmail.com) via the `mcp__9141f369-0875-40fa-8fa0-bba1791de589__create_event` tool, applying the rules below so the user doesn't have to restate them every time.

If the user gives multiple events in one message, create them all in parallel (one tool call per event in the same response).

## Color coding

Pick `colorId` based on what the event is. If two categories could apply, the more specific one wins — e.g. Christine's birthday goes yellow under Birthdays, not pink under Christine, because birthdays-as-a-category override the per-person rule.

| Category | colorId | Color name | What goes here |
|---|---|---|---|
| AVDG work | `9` | Blueberry | Any AVDG shift, including site-tagged ones like `AVDG (Hines)` |
| Trips | `7` | Peacock | Festivals, raves, travel, weekend getaways, road trips |
| Christine | `4` | Flamingo | Anything tied to girlfriend Christine — date nights, her formals, seafood boils with her |
| Friends / gatherings | `10` | Basil | Lunch/dinner with named friends, group hangs, family dinners (Mother's Day etc.) |
| Appointments | `11` | Tomato | Dentist, doctor, haircut, mechanic, consultations |
| Birthdays | `5` | Banana | Anything titled "X's Birthday" |

If the event genuinely fits no category (rare — most things slot in), omit `colorId` and let the calendar default apply.

## Always

- **Timezone**: `America/New_York` for every event. Set `timeZone: "America/New_York"`. For timed events, write start/end with the right offset for the date — `-04:00` during EDT (mid-March → early November) and `-05:00` during EST (early November → mid-March).
- **Calendar**: primary (omit `calendarId`).

## Time handling

- **Start and end given** → use exactly that.
- **Only start given** → default duration by event type:
  - Lunch or dinner with friends/Christine: **2 hours**
  - Appointments (dentist, doctor, haircut, etc.): **1 hour**
  - Anything else: ask once for duration, otherwise default 1 hour
- **No time / "TBD"** → create `allDay: true`, and append ` (Time TBD)` to the title so the user spots it later. Use UTC midnight for start and next-day UTC midnight for end.
- **Multi-day blocks** (trips, festivals, off-work stretches) → `allDay: true`. Remember Google's end date is **exclusive**: a trip from May 29 to May 31 means `start 2026-05-29`, `end 2026-06-01`.
- **Cross-midnight events** (10 PM rave that ends 3 AM) → start time on day 1, end time on day 2.

## Birthdays

Always create birthdays with this exact pattern, regardless of whose:

- `allDay: true`
- `colorId: "5"` (Banana / yellow)
- `recurrenceData: ["RRULE:FREQ=YEARLY"]`
- Title format: `<Name>'s Birthday`
- `timeZone: "America/New_York"`
- Start: `<YYYY>-<MM>-<DD>T00:00:00Z`, End: next day `T00:00:00Z`

Use the current calendar year (2026) for the first occurrence even if that date has already passed — the yearly recurrence will pick up next year. No need to skip ahead.

## AVDG specifics

AVDG is a service job that takes the user to a different client site each day. The base recurring event (Mon–Fri, 8 AM–5 PM ET, Blueberry) already exists. **Don't create new AVDG events** — modify individual instances of the existing recurrence instead.

- **Recurring event ID**: `9vs14op0jp88pfl3p2aabrc3o0`
- **Instance ID format**: `9vs14op0jp88pfl3p2aabrc3o0_<YYYYMMDD>T<HH>0000Z`, where the hour is the UTC hour for 8 AM Eastern that day:
  - During EDT (mid-Mar → early Nov): `T120000Z`
  - During EST (early Nov → mid-Mar): `T130000Z`
- **To tag a day with the client site**: call `update_event` on the instance with `summary: "AVDG (<Site Name>)"`. Leave time and color alone. Always also include `location` from the address book (see **Address auto-lookup** below).
- **Mondays default to `AVDG (Hines)`** unless told otherwise. If the user is mapping out a future week, you can pre-tag Mondays without asking.
- **Day off** (PTO, holiday, sick, traveling): call `delete_event` on that instance, then create a separate all-day event for the reason (e.g. "Memorial Day (Off Work)").

If the recurring event ID stops working (the user recreated AVDG), call `list_events` to find the new one by title, then update this skill with the new ID.

## Address auto-lookup

The user keeps an address book at `~/Documents/Google Calendar/company-addresses.md` (managed by the `/company-address` skill). It's a markdown table of `Company | Address | Notes`. The user has explicitly asked that addresses be applied to events automatically — don't prompt them to confirm.

Any time you're creating or updating an event whose title puts a company name in parentheses (e.g. `AVDG (PAN)`, `Meeting @ Hines`), do this in the same tool call that sets the summary:

1. Extract the company name from inside the parentheses (or from clear context).
2. `Read` the file at `~/Documents/Google Calendar/company-addresses.md`.
3. Case-insensitively find the row whose Company column matches.
4. If found and the Address cell is non-empty, include `location: "<address>"` on the `create_event` / `update_event` call.
5. If the company isn't in the table or the address is blank, skip the `location` field and add one short line to your confirmation: `No address on file for <Company> — say "save <Company> address as <street>" to add it.`

Don't ask the user to confirm the address. Don't narrate the lookup. When the lookup succeeded, a tiny note like `📍 200 Park Ave, NYC` is welcome in the confirmation; otherwise leave it implicit.

## Ambiguity

If the category genuinely isn't clear (e.g. "coffee with someone from work" — friends or appointment?), pick the closest fit, create the event, and mention it briefly so the user can correct.

If the date is missing or relative ("next Friday" with no anchor year, or just "Friday"), resolve to the next future occurrence in the user's local calendar (Eastern). Don't ask just to confirm a year if it's obvious.

## After creating

Reply with one short line per event: title, day + date, time (or "all-day"), and category name. Don't read back the colorId number. Example:

> Added **Lunch with Rosie** — Sat May 2, 12–2 PM (Friends).

If anything is intentionally noteworthy (TBD time, conflicts with an existing event, AVDG already on that day during a trip), flag it in one extra line.
