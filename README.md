# NFL 2026 auto-updating Apple Calendar

This repo hosts `nfl2026.ics` on GitHub Pages and refreshes it automatically from FixtureDownload's NFL 2026 JSON feed.

## Setup

1. Create a free GitHub account if needed, then create a **public** repository named `nfl-2026-calendar`.
2. Upload **all files and folders from this project** to the repository, preserving `.github/workflows/update-calendar.yml`.
3. In the repository, open **Settings → Pages**. Under **Build and deployment**, choose **Deploy from a branch**, select `main` and `/(root)`, then Save.
4. Open the repository's **Actions** tab and enable workflows if GitHub asks. Run **Update NFL calendar** once with **Run workflow** to verify it works.
5. After GitHub Pages publishes, your subscription address will normally be:
   `https://YOUR_GITHUB_USERNAME.github.io/nfl-2026-calendar/nfl2026.ics`
6. On iPhone (iOS 26+), open **Calendar → Calendars → Add Calendar → Add Subscription Calendar**. Paste that HTTPS URL, tap **Find**, name it `🏈 NFL 2026`, choose a color, choose **iCloud** as the account, and tap **Done**.

## What updates automatically

The workflow runs daily at 6:17 AM America/Vancouver time. It refreshes kickoff dates/times and venues from the upstream JSON feed and republishes the ICS. Each game's UID stays stable so calendar clients can update the existing event rather than creating a duplicate.

Late-season TBD games remain date-only placeholders until the feed supplies a non-placeholder kickoff. Exact games use a 3.5-hour duration. No calendar alerts or notifications are embedded in the ICS file.

## Notes

- GitHub Pages is public. This is fine for an NFL schedule, but anyone with the URL can subscribe.
- The upstream FixtureDownload feed says it is normally updated once per day and its schema may change. If the feed format changes, the updater may need adjustment.
- Apple decides when subscribed calendars refresh; changes are not guaranteed to appear instantly.
- `calendar_template.ics`, `template_metadata.json`, and `venue_addresses.json` preserve the richer formatting and stadium addresses used by the generator.
