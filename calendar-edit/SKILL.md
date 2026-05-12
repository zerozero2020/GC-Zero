---
name: calendar-edit
description: Modify an existing event on the user's Google Calendar — change date, time, location, title, notes, color, or any detail — instead of creating a duplicate. Use this skill whenever the user says "/calendar edit" or "/calendar-edit", or asks to move, reschedule, push back, update, change, fix, add notes to, add a location to, attach an address to, or otherwise modify an event that's already on their calendar. Prefer this over calendar-add whenever the user references an event by name or implies "the one I already have" — e.g. "move lunch with Rosie to 1 PM," "change my dentist to next week," "add the address to Vicki and Jason," "Christine's Formals will be at 5 PM now." Trust this skill rather than asking for clarification on the basics.
---

# /calendar edit

Modify an existing event on the user's primary Google Calendar (zerobitches2020@gmail.com) instead of creating a new one. The whole point is to keep the calendar clean — when something changes, edit the existing event in place rather than adding a duplicate.

Primary tools:
- `mcp__9141f369-0875-40fa-8fa0-bba1791de589__list_events` — to find the event
- `mcp__9141f369-0875-40fa-8fa0-bba1791de589__get_event` — to read its current state before relative changes
- `mcp__9141f369-0875-40fa-8fa0-bba1791de589__update_event` — to apply changes
- `mcp__9141f369-0875-40fa-8fa0-bba1791de589__delete_event` and `create_event` — only for the all-day ↔ timed conversion (see below)

## Step 1: Find the event

You need an event ID before you can update anything. Approaches in order of preference:

1. **Date + title is given** (e.g. "Lunch with Rosie on May 2"): call `list_events` with `fullText` set to the keyword and a narrow `startTime`/`endTime` window (the given day plus or minus one day). Match the result.
2. **Title only, no date** (e.g. "the dentist appointment"): call `list_events` with `fullText` keyword, `startTime = now`, `endTime = +90 days`. If nothing comes back, expand to the past 30 days — past events can still be edited (e.g. adding notes after the fact).
3. **Date only, no title** (e.g. "the thing on Saturday"): call `list_events` for that day's window and list everything back to the user to confirm.

**If multiple events match**, list the candidates (title, date, start time) and ask which one to edit. Don't guess between two plausible matches.

**If nothing matches**, tell the user — and ask whether they want to add it via `/calendar add` instead. Don't silently fall through to creating an event; that defeats the purpose of this skill.

## Step 2: Read current state when needed

Before applying a **relative** change (e.g. "push the dentist back an hour," "add to the existing description"), call `get_event` to see the current values. Otherwise you'll lose information — `update_event` replaces the field you pass, so appending a note means reading the old description, concatenating, and writing the combined string back.

You don't need `get_event` for an absolute change ("move it to 3 PM," "rename it to X"). The list_events result usually has enough to confirm the right event was found.

## Step 3: Apply the edit

Pass only the fields that are changing. Anything you don't pass stays untouched.

- **New date or time** → set `startTime` and `endTime` with `timeZone: "America/New_York"` and the right offset for that date (`-04:00` during EDT mid-March → early November, `-05:00` during EST early November → mid-March).
- **New title** → `summary`.
- **Location** → `location` (free-form text — full address is best: `"Carbone, 181 Thompson St, New York, NY"`).
- **Notes / details / description** → `description`. **Append, don't overwrite**, unless the user is explicitly rewriting the whole note. Format: `<existing description>\n\n<new note>`.
- **Category change** → `colorId` (legend below).
- **Attendees** → `addedAttendeeEmails` and `removedAttendeeEmails`.

## Color legend (same as calendar-add)

| Category | colorId | Color |
|---|---|---|
| AVDG work | `9` | Blueberry |
| Trips (festivals, raves, travel) | `7` | Peacock |
| Christine | `4` | Flamingo |
| Friends / gatherings | `10` | Basil |
| Appointments | `11` | Tomato |
| Birthdays | `5` | Banana |

## Recurring events: AVDG and Birthdays

**AVDG** is a recurring Mon–Fri block. Two cases:

- **Just one day** (most edits — adding a site tag like `AVDG (Hines)`, a one-off time change, etc.): operate on the **instance ID**, not the recurring event ID.
  - Recurring event ID: `9vs14op0jp88pfl3p2aabrc3o0`
  - Instance ID format: `9vs14op0jp88pfl3p2aabrc3o0_<YYYYMMDD>T120000Z` during EDT, or `T130000Z` during EST
  - `list_events` returns the specific instance for the day you query, with the correct ID.
- **All future occurrences** (rare — e.g. hours change permanently from 8–5 to 9–6): operate on the recurring event ID itself.

**Birthdays** are yearly recurring. If the user is correcting the date, update the parent event — Google adjusts all future occurrences automatically. Don't try to edit a single year's instance unless the user is making a one-time-only change for that year.

**Day off from AVDG** (PTO, holiday, sick, travel): delete that day's instance with `delete_event`, then create a separate all-day event for the reason. This was how Memorial Day got handled.

## Address auto-lookup (AVDG and on-site events)

The user keeps an address book at `~/Documents/Google Calendar/company-addresses.md` (managed by the `/company-address` skill). It's a `Company | Address | Notes` markdown table. The user has explicitly asked that addresses be applied automatically — don't ask for confirmation.

Whenever the edit involves tagging or retagging an event with a company name in parentheses (e.g. `AVDG (PAN)`, `Meeting at Hines`):

1. Extract the company name.
2. `Read` `~/Documents/Google Calendar/company-addresses.md`.
3. Case-insensitively match against the Company column.
4. If found and the Address cell is non-empty, include `location: "<address>"` in the same `update_event` call.
5. If not found or blank, just skip the location and add one line to your confirmation: `No address on file for <Company> — say "save <Company> address as <street>" to add it.`

If the user is explicitly setting a different location for that one event, their explicit value wins — don't override it with the address book.

## The all-day ↔ timed gotcha

`update_event` does **not** reliably convert an event between all-day and timed. Symptoms: it ignores the new times, leaves the event as all-day on a shifted date, or zeroes out the duration. We hit this with Candice's Birthday Event — had to delete and recreate.

When the user is converting an event between formats (TBD all-day → timed, or timed → all-day), do this:

1. Read the existing event's details (summary, colorId, description, location, attendees, recurrenceData, etc.) — use `get_event` if you don't already have them.
2. Call `delete_event` on the old event.
3. Call `create_event` with the new format and **all** the carried-over fields.

Within the same format (all-day → different day, or timed → different time), regular `update_event` works fine.

When you do a delete-and-recreate, mention it in the confirmation so the user knows the event ID changed (any links or RSVPs from the old event are gone).

## Ambiguity rules

- **Relative shift with no anchor** ("push the dentist back an hour"): find the next future occurrence and apply the shift. If there's no future occurrence, find the most recent past one and ask if that's the one they mean.
- **Recurring event, "just this one" vs "all of them" unclear**: default to **just this instance** — it's the safer move. Mention which you did so the user can correct.
- **User says "edit" but the change is really an addition** (e.g. "add a second lunch on the same day"): that's a `/calendar add` case, not an edit. Hand it off.
- **Date is missing on a change like "move to 5 PM"**: assume same day as the current event. Only ask if the existing event is also undated (a TBD all-day).

## After editing

Reply with one short line per change: title, what was modified, the new value. Examples:

> Updated **Lunch with Rosie** — moved to 1–3 PM, Sat May 2.

> Updated **Christine's Formals** — time set to 5–9 PM, location added (The Plaza, NYC).

> Updated **AVDG (Tue May 12)** — site tag changed to `AVDG (Asana)`.

If the all-day ↔ timed gotcha forced a delete-and-recreate, add one line:

> Note: had to recreate the event to change the time format — the old event ID is gone.

If anything ambiguous happened (picked one of several matches, defaulted to single-instance on a recurrence, etc.), flag it in one extra line so the user can correct.
