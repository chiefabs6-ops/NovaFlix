"""English-dub release estimates from AnimeSchedule.net (DEC-056).

Uses the public anime endpoint only (no token). Timetables need an app token
and are not used. Field meanings from the v3 API documentation:
- dubPremier: release date of the first dubbed episode.
- dubTime: release time; only hour and minute are relevant.
- dubDelayedFrom/Until: a break in the weekly dub schedule.
- dubEpisodeOverride: on overrideDate, episodes overrideEpisode ..
  overrideEpisode + episodesAired came out together ("7-12" is 7 and 5).
Dates of 0001-01-01 mean "not set".

The result is an estimate: weekly from the premiere, shifted by known breaks.
"""

import datetime

from resources.lib.net import http

URL = "https://animeschedule.net/api/v3/anime"
WEEK = datetime.timedelta(days=7)


def fetch(mal_id):
    """The entry for this MAL ID, or None if AnimeSchedule has none."""
    data = http.get(URL, params={"mal-ids": int(mal_id)}).json() or {}
    for entry in data.get("anime") or []:
        mal_url = (entry.get("websites") or {}).get("mal") or ""
        if f"/anime/{int(mal_id)}/" in mal_url + "/":
            return entry
    return None


def _date(value):
    """'2026-02-06T00:00:00Z' -> date, or None for missing / year-1 values."""
    try:
        day = datetime.date.fromisoformat((value or "")[:10])
    except ValueError:
        return None
    return day if day.year > 1 else None


def _time(value):
    try:
        return datetime.time(int(value[11:13]), int(value[14:16]))
    except (TypeError, ValueError):
        return datetime.time(0, 0)


def dub_schedule(entry):
    """Compact, cacheable dub schedule, or None if no dub is announced."""
    premier = _date(entry.get("dubPremier"))
    if premier is None:
        return None
    at = _time(entry.get("dubTime"))
    delays = []
    delay_from = _date(entry.get("dubDelayedFrom"))
    if delay_from:
        delay_until = _date(entry.get("dubDelayedUntil"))
        delays.append([delay_from.isoformat(), delay_until.isoformat() if delay_until else None])
    override = None
    raw = entry.get("dubEpisodeOverride") or {}
    override_date = _date(raw.get("overrideDate"))
    if override_date and raw.get("overrideEpisode"):
        override = {"date": override_date.isoformat(), "episode": int(raw["overrideEpisode"]),
                    "extra": int(raw.get("episodesAired") or 0)}
    return {
        "premier": datetime.datetime.combine(premier, at, datetime.timezone.utc).isoformat(),
        "delays": delays,
        "override": override,
    }


def _estimate(schedule, number):
    start = datetime.datetime.fromisoformat(schedule["premier"])
    override = schedule["override"]
    if override and number >= override["episode"]:
        anchor = datetime.datetime.combine(datetime.date.fromisoformat(override["date"]), start.timetz())
        last_in_drop = override["episode"] + override["extra"]
        date = anchor + WEEK * max(0, number - last_in_drop)
    else:
        anchor = start
        date = start + WEEK * (number - 1)
    for delay_from, delay_until in schedule["delays"]:
        begins = datetime.date.fromisoformat(delay_from)
        if anchor.date() < begins <= date.date():
            if delay_until is None:
                return None  # delayed with no end date: nothing to estimate
            date += datetime.date.fromisoformat(delay_until) - begins
    return date


def estimates(schedule, numbers):
    """{episode number: estimated UTC datetime} for the numbers that can be estimated."""
    out = {}
    for number in numbers:
        try:
            date = _estimate(schedule, number)
        except OverflowError:
            break  # past year 9999: later numbers are further out still
        if date is not None:
            out[number] = date
    return out
