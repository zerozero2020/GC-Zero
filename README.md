# Google Calendar — Personal Skill Set

Three skills work together to manage your Google Calendar with your personal conventions baked in. Everything in this folder is what you and Claude built together — the `.skill` files are the installable bundles, the subfolders contain the source, and `company-addresses.md` is the data file the skills read from.

## The three skills

### `/calendar-add` — `calendar-add.skill`

Creates new events with your color-coding and time defaults applied automatically. Knows the difference between birthdays (yellow, yearly), trips (light blue, all-day), Christine (pink), friends (green), appointments (red), and AVDG work (blue). Eastern timezone by default. Lunch/dinner default to 2 hours, appointments to 1 hour, TBD events become all-day with a `(Time TBD)` label.

For AVDG specifically: it updates the existing recurring event's instances rather than creating duplicates, defaults Mondays to Hines, and pulls the location from the address book (see below).

### `/calendar-edit` — `calendar-edit.skill`

Modifies events already on the calendar instead of creating duplicates. Finds the event by title (with optional date narrowing), reads its current state when you ask for a relative change ("push back an hour," "add to the notes"), and applies the edit in place. Handles the all-day ↔ timed conversion gotcha by auto-falling-back to delete-and-recreate when needed. Defaults to "just this instance" on recurring events unless you say otherwise.

### `/company-address` — `company-address.skill`

Maintains the address book at `company-addresses.md` in this folder. Use it to save, update, look up, or list addresses for your AVDG client sites (and anywhere else you tend to forget). Whenever calendar-add or calendar-edit creates or modifies an event tagged with a known company name (e.g. `AVDG (Hines)`), it silently looks up the address here and fills in the event's location — so when you check your calendar before heading out, the address is right there.

## How they share state

```
~/Documents/Google Calendar/
├── README.md                       ← this file
├── company-addresses.md            ← the address book (data)
├── calendar-add.skill              ← installable bundle
├── calendar-edit.skill             ← installable bundle
├── company-address.skill           ← installable bundle
├── calendar-add/SKILL.md           ← source for calendar-add
├── calendar-edit/SKILL.md          ← source for calendar-edit
└── company-address/SKILL.md        ← source for company-address
```

The `.skill` files are the things you install. The folders next to them are the source — kept here so you (or Claude in a future session) can read or tweak them without unzipping the bundle. If you change a `SKILL.md` source file, ask Claude to repackage the corresponding `.skill` and reinstall it.

The `company-addresses.md` file is plain markdown and you can edit it directly in any text editor. It's the source of truth that all three skills read from.

## Color legend (kept consistent across both calendar skills)

| Category | Google Calendar color | Examples |
|---|---|---|
| AVDG work | Blueberry (blue) | Any AVDG shift, including site-tagged ones like `AVDG (Hines)` |
| Trips | Peacock (light blue) | Festivals, raves, travel, weekend getaways |
| Christine | Flamingo (pink) | Anything tied to your girlfriend Christine |
| Friends / gatherings | Basil (green) | Lunch/dinner with named friends, group hangs, family dinners |
| Appointments | Tomato (red) | Dentist, doctor, haircut, mechanic, consultations |
| Birthdays | Banana (yellow) | Anything titled `<Name>'s Birthday` |

## Things to remember

- **Timezone**: everything defaults to Eastern (`America/New_York`). Your Google Calendar's display timezone is a separate setting — make sure that's set to New York too if you want events to *display* at the times you typed.
- **AVDG recurring event ID** is currently `9vs14op0jp88pfl3p2aabrc3o0`. If you ever recreate the AVDG block, ask Claude to update the skills with the new ID.
- **End dates are exclusive** for all-day blocks. A trip from May 29–31 means start `2026-05-29`, end `2026-06-01`. The skills handle this for you, but it's good to know if you're editing directly in Google Calendar.

## Future ideas to revisit

- Auto-summary at end of week / beginning of month
- Sync birthdays to a separate calendar so they can be toggled off when you don't want yellow flooding the view
- Travel-time padding before AVDG site visits using the address book + driving time
- A `/calendar-look` skill that summarizes upcoming events without you having to open Google Calendar
