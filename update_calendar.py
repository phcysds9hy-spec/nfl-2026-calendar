#!/usr/bin/env python3
"""Rebuild nfl2026.ics from the free FixtureDownload NFL 2026 JSON feed.

The published VEVENT UIDs are deterministic and never change, which lets subscribed
calendar clients update an existing game when kickoff time/location changes.
"""
from pathlib import Path
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import argparse, json, re, urllib.request

ROOT=Path(__file__).resolve().parent
FEED='https://fixturedownload.azurewebsites.net/feed/json/nfl-2026'
VAN=ZoneInfo('America/Vancouver')
ET=ZoneInfo('America/New_York')
UTC=timezone.utc


def slug(s):
    s=s.lower().replace('&','and')
    s=re.sub(r'[^a-z0-9]+','-',s).strip('-')
    return s


def uid_for(g):
    return f"2026-{g['RoundNumber']}-{slug(g['AwayTeam'])}-at-{slug(g['HomeTeam'])}@dani-nfl-calendar"


def esc(s):
    return str(s).replace('\\','\\\\').replace('\n','\\n').replace(';','\\;').replace(',','\\,')


def fold(line):
    # RFC 5545: content lines should be no longer than 75 octets.
    out=[]; prefix=''
    remaining=line
    limit=75
    while remaining:
        chunk=''
        for ch in remaining:
            if len((prefix+chunk+ch).encode('utf-8')) > limit:
                break
            chunk += ch
        if not chunk:  # defensive for an unusually wide character
            chunk=remaining[0]
        out.append(prefix+chunk)
        remaining=remaining[len(chunk):]
        prefix=' '
        limit=75
    return '\r\n'.join(out) if out else ''


def prop(name, value, text=False):
    return fold(f"{name}:{esc(value) if text else value}")


def load_json(name):
    return json.loads((ROOT/name).read_text(encoding='utf-8'))


def fetch_schedule(offline=False):
    if offline:
        return load_json('seed_schedule.json')
    req=urllib.request.Request(FEED,headers={'User-Agent':'Dani-NFL-Calendar/1.0'})
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            return json.load(r)
    except Exception as e:
        print(f'WARNING: live feed failed ({e}); using seed schedule.')
        return load_json('seed_schedule.json')


def parse_feed_dt(s):
    return datetime.strptime(s,'%Y-%m-%d %H:%M:%SZ').replace(tzinfo=UTC)


def parse_template_dt(s):
    if not s: return None
    return datetime.strptime(s,'%Y%m%dT%H%M%SZ').replace(tzinfo=UTC)


def special_label(g, dt, full_location, unchanged, meta):
    if unchanged and meta.get('summary') and not meta.get('date_only'):
        # Preserve manually curated holiday/international labels while the event is unchanged.
        return meta['summary'].split(' — ')[0].replace('🏈 ','')
    if g.get('MatchNumber') == 1:
        return 'NFL Kickoff Game'
    international = full_location and not full_location.rstrip().endswith('USA')
    if international:
        return 'International Game'
    et=dt.astimezone(ET)
    wd=et.weekday()  # Mon=0
    if wd==3 and et.hour>=19: return 'Thursday Night Football'
    if wd==6 and et.hour>=19: return 'Sunday Night Football'
    if wd==0 and et.hour>=19: return 'Monday Night Football'
    if wd==5: return 'NFL Saturday'
    return f"NFL Week {g['RoundNumber']}"


def make_event(g, meta, full_location, now, seq):
    uid=uid_for(g)
    source_dt=parse_feed_dt(g['DateUtc'])
    initial_dt=parse_template_dt(meta.get('initial_dtstart'))

    # A game that started as a date-only placeholder remains TBD until the live feed
    # moves away from its placeholder timing. FixtureDownload currently encodes TBD
    # late-season games at exactly 00:00 UTC; normal NFL kickoffs in this feed are not.
    still_tbd = bool(meta.get('date_only')) and source_dt.hour==0 and source_dt.minute==0
    changed = initial_dt is not None and source_dt != initial_dt
    unchanged = not changed and not meta.get('date_only')

    lines=['BEGIN:VEVENT', prop('UID',uid), prop('DTSTAMP',now.strftime('%Y%m%dT%H%M%SZ')),
           prop('LAST-MODIFIED',now.strftime('%Y%m%dT%H%M%SZ')), prop('SEQUENCE',str(seq))]

    if still_tbd:
        ph=meta.get('placeholder_date') or source_dt.astimezone(VAN).strftime('%Y%m%d')
        start=datetime.strptime(ph,'%Y%m%d').date()
        end=start+timedelta(days=1)
        lines += [prop('DTSTART;VALUE=DATE',start.strftime('%Y%m%d')),
                  prop('DTEND;VALUE=DATE',end.strftime('%Y%m%d')),
                  prop('STATUS','TENTATIVE'), prop('TRANSP','TRANSPARENT')]
        summary=f"⚠️ TBD — NFL Week {g['RoundNumber']} — {g['AwayTeam']} @ {g['HomeTeam']}"
        cats=f"NFL,Football,Week {g['RoundNumber']},TBD/Flex"
        desc=(f"{g['AwayTeam']} at {g['HomeTeam']}\nNFL Week {g['RoundNumber']}\nVenue: {g['Location']}\n"
              "Exact date/kickoff is still subject to NFL late-season scheduling. This subscribed calendar will update when the upstream schedule changes.\n"
              "Broadcast: TBD; see NFL/local Canadian listings\nSchedule source: FixtureDownload NFL 2026 JSON feed.")
        lines += [prop('SUMMARY',summary,True), prop('LOCATION',full_location or g['Location'],True),
                  prop('CATEGORIES',cats,True), prop('DESCRIPTION',desc,True)]
    else:
        enddt=source_dt+timedelta(hours=3,minutes=30)
        lines += [prop('DTSTART',source_dt.strftime('%Y%m%dT%H%M%SZ')),
                  prop('DTEND',enddt.strftime('%Y%m%dT%H%M%SZ')),
                  prop('STATUS','CONFIRMED'), prop('TRANSP','OPAQUE')]
        label=special_label(g,source_dt,full_location,unchanged,meta)
        summary=f"🏈 {label} — {g['AwayTeam']} @ {g['HomeTeam']}"
        cats=f"NFL,Football,Week {g['RoundNumber']}"
        if 'Night Football' in label: cats += ','+label
        if label=='International Game': cats += ',International Game,International'
        broadcast=meta.get('broadcast','See NFL/local Canadian listings') if unchanged else 'See NFL/local Canadian listings'
        van=source_dt.astimezone(VAN); et=source_dt.astimezone(ET)
        desc=(f"{g['AwayTeam']} at {g['HomeTeam']}\nNFL Week {g['RoundNumber']}\nVenue: {g['Location']}\n"
              f"Kickoff: {van.strftime('%a %b %-d, %-I:%M %p %Z')} / {et.strftime('%-I:%M %p ET')}\n"
              f"Broadcast: {broadcast}\nEvent duration is set to 3h 30m. Kickoff is stored in UTC so iPhone Calendar converts it automatically if your timezone changes.\n"
              "Schedule source: FixtureDownload NFL 2026 JSON feed; calendar generated automatically.")
        if g.get('HomeTeamScore') is not None and g.get('AwayTeamScore') is not None:
            desc += f"\nResult: {g['AwayTeam']} {g['AwayTeamScore']} – {g['HomeTeamScore']} {g['HomeTeam']}"
        lines += [prop('SUMMARY',summary,True), prop('LOCATION',full_location or g['Location'],True),
                  prop('CATEGORIES',cats,True), prop('DESCRIPTION',desc,True)]
    lines.append('END:VEVENT')
    return '\r\n'.join(lines)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--offline',action='store_true',help='Use bundled seed schedule (for testing).')
    args=ap.parse_args()
    metadata=load_json('template_metadata.json')
    addresses=load_json('venue_addresses.json')
    games=fetch_schedule(args.offline)
    if len(games) < 272:
        raise SystemExit(f'Refusing to publish: expected 272 games, received {len(games)}')
    now=datetime.now(UTC).replace(microsecond=0)
    seq=int((now-datetime(2026,1,1,tzinfo=UTC)).total_seconds()//60)
    events=[]
    missing=[]
    for g in games:
        uid=uid_for(g)
        meta=metadata.get(uid,{})
        if not meta: missing.append(uid)
        full=addresses.get(g['Location'],g['Location'])
        events.append(make_event(g,meta,full,now,seq))
    if missing:
        print(f'WARNING: {len(missing)} games were not in template metadata; generic formatting used.')
    header=[
        'BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Dani NFL Calendar//NFL 2026 Subscribed//EN',
        'CALSCALE:GREGORIAN','METHOD:PUBLISH',
        prop('X-WR-CALNAME','NFL 2026 Regular Season',True),
        prop('X-WR-CALDESC','Auto-updating 2026 NFL regular-season calendar. Times stored in UTC; late-season TBD games update when announced.',True),
        'X-WR-TIMEZONE:America/Vancouver','REFRESH-INTERVAL;VALUE=DURATION:PT6H','X-PUBLISHED-TTL:PT6H',
        prop('X-WR-LAST-CHECKED',now.strftime('%Y-%m-%dT%H:%M:%SZ'))
    ]
    out='\r\n'.join(header)+'\r\n'+'\r\n'.join(events)+'\r\nEND:VCALENDAR\r\n'
    (ROOT/'nfl2026.ics').write_text(out,encoding='utf-8',newline='')
    print(f'Wrote {len(games)} events to nfl2026.ics')

if __name__=='__main__': main()
