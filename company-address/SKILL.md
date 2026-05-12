---
name: company-address
description: Save, look up, or update the address of a company / client site that shows up in the user's calendar. Use this skill whenever the user says "/company-address", "/address", or anything like "save the address for Hines as 123 Main St," "what's the address for PAN," "update Hunterdon Health's address to...," "add a new site called X," or "list the addresses I have saved." Also use it as a lookup step (silently, in the background) before creating or editing any AVDG / on-site calendar event so the event's location field gets filled in automatically. The user explicitly wants this auto-applied — they're forgetful about where sites are and the calendar is where they check.
---

# /company-address

Manages a personal address book of companies and client sites the user visits for work. The data lives in:

```
~/Documents/Google Calendar/company-addresses.md
```

That file is a human-readable markdown table with columns `Company | Address | Notes`. The user can also edit it directly by hand — treat the file as the source of truth.

## When to use this skill

Two distinct modes:

1. **User-facing CRUD** — they invoke you to add, change, look up, or list company addresses. Use the operations below.
2. **Background lookup** — any time the calendar-add or calendar-edit skill is about to create or modify an event that involves an on-site company (most commonly an `AVDG (<Company>)` event), look up the company's address from this file and pass it as the `location` field on the create/update call. Do this silently — don't ask the user, just include it. If the company isn't in the file, skip the location field and mention it once in the confirmation so the user knows to add the address.

## Reading the file

Use the `Read` tool on `~/Documents/Google Calendar/company-addresses.md`. The file is small enough to read in one shot. Parse the markdown table to get rows. Match on the Company column case-insensitively (so `AVDG (hines)` and `AVDG (Hines)` both find the same row).

## Operations

### Add a new company

User says something like "save Hines as 200 Park Ave, NYC" or "/company-address add Hines, 200 Park Ave, NYC".

1. Read the current file.
2. If the company isn't in the table, add a new row at the bottom.
3. If the company is already there with an empty address, fill the address in.
4. If the company is already there with a different address, ask the user whether to overwrite — don't silently replace a real address.
5. Write the file back.

### Update an existing address

User says "change PAN's address to ..." or "PAN moved, new address is ...".

1. Read the file.
2. Find the row (case-insensitive on Company).
3. Replace the Address cell.
4. Write the file back.

### Look up an address

User asks "what's the address for X" or "where is X again".

1. Read the file.
2. Return the address and any notes for that company.
3. If not found, say so and offer to add it.

### List all addresses

User says "what addresses do I have," "list my sites," etc.

Read the file and reply with the table contents in a compact form. Group companies with addresses vs. ones still missing addresses so the user can see what's filled in.

### Remove a company

User says "remove Foo" or "delete Bar's address".

Remove the row entirely. Confirm before saving so they don't lose data by mistake.

## Background lookup pattern (for calendar-add and calendar-edit)

When another skill is creating or editing an event:

1. If the event title matches the pattern `AVDG (<Company>)` (or any other on-site indicator), extract the company name from inside the parentheses.
2. Read `~/Documents/Google Calendar/company-addresses.md`.
3. Case-insensitively find a matching row.
4. If found and the Address cell is non-empty, pass `location: "<address>"` to `create_event` or `update_event`.
5. If not found or the address is blank, skip the location field. In the post-create/edit confirmation, add one short line: `No address on file for <Company> — say "save <Company> address as <street>" to add it.`

Don't prompt the user to confirm the address. They've already said they want this automatic.

## Writing back to the file

When updating the markdown file:

- Preserve the existing structure (header, intro paragraph, table headers).
- Keep rows alphabetically sorted by Company name — easier for the user to scan visually.
- Use `Edit` (string replace) for single-row changes; use `Write` only if you're rewriting the whole table.
- Always include all three columns (`Company | Address | Notes`) — leave a cell blank rather than dropping it.

## Address format

Don't enforce a strict format — the user types what's useful to them. But aim for something a maps app would accept (street, city, state). If the user gives partial info, save what they gave and don't pester for more.

## After any change

Reply with one short line:

> Saved **Hines** — 200 Park Ave, New York, NY.

> Updated **PAN** — address changed to 50 Hudson Yards.

> Removed **Citrin Cooperman**.

For lookups:

> **PAN** — 50 Hudson Yards, New York, NY.

For lists, use a tight bullet list with company → address; group empties at the bottom under a short header.
