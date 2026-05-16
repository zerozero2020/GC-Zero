# Bot Roadmap

Planned features in rough priority order. The goal is a single Telegram interface
for managing multiple areas of life, starting with Google Calendar.

---

## Pending setup (not code)

- [ ] **Shane — Project Cook access**: Get Shane's Telegram chat ID (@userinfobot),
  add it to `PC_COLLABORATOR_IDS` in the Railway dashboard.

---

## In progress / next up

- [x] **Task list** — `/task add`, `/task done`, `/task delete`, `/task clear`
- [x] **Quick notes** — `/note <text>`, `/notes`, `/note delete <#>`
- [ ] **Gmail integration** — summarize emails, create events from threads *(on hold — revisit once Gmail is organized)*

---

## Backlog

- [ ] **Expense logging** — `/spent $45 groceries` → log to spreadsheet or file
- [ ] **Reminder editing** — `/edit dentist, May 15 > remind 30` on existing events
- [ ] **Multi-day trip editing** — shift both start and end of a date range via `/edit`
- [ ] **Search** — find events by title without knowing the date

---

## Completed

- [x] `/add` with natural language dates, color inference, batch mode
- [x] `/edit` — time, date, date+time, location, title, category
- [x] `/delete` — single and batch
- [x] `/avdg` — workday tagging with address lookup
- [x] `/today`, `/tomorrow`, `/week`, `/summary`, `/on <date>`
- [x] Multi-day events with `-` date range
- [x] Per-event reminders (`remind 30`, `remind 1h`, `remind 1d`)
- [x] Project Cook calendar with `[pc]` prefix routing
- [x] Multi-user access control (owner + collaborators via `PC_COLLABORATOR_IDS`)
- [x] Task list (`/task add`, `/task done`, `/task delete`, `/task clear`)
- [x] Quick notes (`/note`, `/notes`, `/note delete`)
- [x] Daily 7am morning briefing
- [x] Sunday 8pm weekly preview notification
