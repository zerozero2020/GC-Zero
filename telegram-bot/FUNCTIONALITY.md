# Calendar Bot — Functionality Reference

A personal Telegram bot that manages Google Calendar via natural-language commands.
Hosted on Heroku, built with FastAPI + Python.

---

## Commands

### `/add <title>, <date/time> [remind X]`

Creates one or more calendar events. The bot auto-assigns a color category based on
keywords in the title and asks you to pick one if it can't determine it automatically.

**Examples:**
```
/add Dentist, tomorrow 2pm
/add Lunch with Rosie, May 17 noon
/add Doctor, June 1 9am remind 30
/add Doctor, June 1 9am remind 1h
/add Coachella trip, April 11-13
/add Mom's Birthday, March 15
/add Trip to Japan, August 6th - August 9th
```

**Reminders:** Append `remind X` to the date/time to set a popup reminder.
- `remind 30` = 30 minutes before
- `remind 1h` or `remind 2h` = hours before
- `remind 1d` = 1 day before

**Batch mode:** Separate multiple events with ` : `
```
/add Dentist, May 15 2pm : Gym, May 16 7am
```

**Project Cook calendar:** Prefix with `[pc]`
```
/add [pc] Team meeting, June 3 2pm
```

**Auto-color rules:**

| Keyword(s) in title | Color | Category |
|---|---|---|
| birthday | Banana | Birthday — yearly recurring |
| avdg | Blueberry | AVDG |
| trip, festival, rave, travel, vacation, flight | Peacock | Trip |
| christine | Flamingo | Christine |
| dentist, doctor, haircut, mechanic, appointment, physical | Tomato | Appt |
| Capitalized name detected | Basil | Friends |
| Uncertain | — | Bot asks you to pick |

---

### `/edit <title>, <date> > <change>`

Edits an existing event. Finds the event by title + date, then applies the change.

**Time change (keeps original date):**
```
/edit dentist, May 15 > 3pm
```

**Date move (keeps original time):**
```
/edit dentist, May 15 > May 20
```

**Date + time move:**
```
/edit dentist, May 15 > May 20 3pm
```

**Category/color:**
```
/edit dentist, May 15 > category friends
/edit dentist, May 15 > category 1
```
Valid: `friends`, `trip`, `appt`, `birthday`, `avdg`, `christine`, `none` (or numbers 1–7).

**Location:**
```
/edit dentist, May 15 > location 123 Main St
```

**Rename:**
```
/edit lunch Rosie, May 17 > title Dinner with Rosie
```

**Project Cook:**
```
/edit [pc] meeting, June 3 > 3pm
```

Moving an all-day event requires a date (e.g. `May 20`). Multi-day events preserve
their duration when moved.

---

### `/delete <title>, <date>`

Deletes an event by title + date. If multiple events match, the bot lists them and
asks you to be more specific.

**Examples:**
```
/delete dentist, May 15
/delete [pc] team meeting, June 3
```

**Batch mode:**
```
/delete dentist, May 15 : gym, May 16
```

**Date ranges** (finds events spanning the range):
```
/delete Japan trip, August 6th - August 9th
```

---

### `/avdg <site> <day>`

Manages AVDG workday events on the recurring calendar entry.

- Updates the recurring AVDG event with a site name and looks up its address from
  the address book (`company-addresses.md`).
- `off` removes AVDG and creates an "Off Work" event instead.

**Examples:**
```
/avdg Hines Monday
/avdg PAN Tue May 19
/avdg off Wednesday
```

---

### `/on <date>`

Shows events on any specific day across all calendars.

```
/on tomorrow
/on Friday
/on June 3
/on next Monday
```

---

### `/tomorrow`

Shows tomorrow's events across all calendars.

---

### `/today`

Shows all events today, across all calendars (Calendar Zero + Project Cook).

---

### `/week`

Shows all events in the next 7 days, across all calendars.

---

### `/summary`

Shows remaining events this week grouped by day with bold day headings,
across all calendars.

---

### `/task`

Personal task list backed by SQLite. Numbers are positional in the open list.

```
/task                   ← same as /task list
/task list
/task add Call dentist
/task done 1
/task delete 2
/task clear             ← removes all completed tasks
```

> **Railway note:** `tasks.db` lives on the container filesystem. Set up a
> Railway persistent volume mounted at the `telegram-bot/` directory to survive
> redeploys. Without it, tasks reset on each deploy.

---

### `/suggestions <note>`

Saves a note to `suggestions.md` in the bot directory with a timestamp.
Use this to log ideas for improving the bot from your phone.

```
/suggestions add a /tomorrow command
```

---

### `/help` or `/start`

Displays the command reference in Telegram.

---

## Automatic Notifications

**Daily 7:00 AM ET** — Morning briefing with today's events sent automatically.

**Sunday 8:00 PM ET** — Preview of the following week's events, grouped by day.

---

## Calendars

| Prefix | Calendar |
|---|---|
| *(none)* | Calendar Zero (primary) |
| `[pc]` | Project Cook (shared with collaborator) |

Read commands (`/today`, `/tomorrow`, `/week`, `/on`, `/summary`, Sunday preview)
always show events from **all calendars** merged and sorted by start time.

## Access Control

| Role | How to set | Access |
|---|---|---|
| Owner | `OWNER_CHAT_ID` env var | All commands |
| Collaborator | `PC_COLLABORATOR_IDS` env var (comma-separated chat IDs) | Read commands + `[pc]`-prefixed `/add`, `/edit`, `/delete` |
| Unknown | — | Silently ignored |

To add a collaborator, get their Telegram chat ID (they can message @userinfobot)
and add it to `PC_COLLABORATOR_IDS` in the Railway dashboard.

---

## Infrastructure

- **Platform:** Railway (auto-deploys from GitHub main branch)
- **Procfile:** `web: uvicorn main:app --host 0.0.0.0 --port $PORT` (inside `telegram-bot/`)
- **Webhook:** Telegram sends updates to `/webhook/{token}`
- **Scheduler:** APScheduler — morning briefing 7:00 AM ET daily, weekly summary Sunday 8:00 PM ET
- **Auth:** Google OAuth2 via refresh token (env vars: `GOOGLE_CLIENT_ID`,
  `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`)
- **Internal endpoints:**
  - `POST /setup-webhook` — register Telegram webhook after deploy
  - `POST /test-morning-briefing` — manually trigger the morning briefing
  - `POST /test-weekly-summary` — manually trigger the Sunday notification
  - `GET /health` — liveness check
