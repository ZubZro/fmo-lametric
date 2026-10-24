#!/usr/bin/env python3
"""Build a chronologically sorted LaMetric feed for Münster/Osnabrück Airport."""

import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

URL = "https://service.fmo.de/arrdep1.xml"
TZ = ZoneInfo("Europe/Berlin")
OUT = Path("public/data.json")
DELAY_THRESHOLD_MINUTES = 10


def tag_name(tag):
    return tag.rsplit("}", 1)[-1].strip().upper()


def values(flight):
    return {
        tag_name(child.tag): (child.text or "").strip()
        for child in list(flight)
    }


def parse_datetime(data, prefix):
    date = data.get(prefix + "_DATE", "")
    time = data.get(prefix + "_TIME", "")
    if not date or not time:
        return None

    for fmt in (
        "%d.%m.%Y %H:%M",
        "%Y-%m-%d %H:%M",
        "%d.%m.%y %H:%M",
        "%Y%m%d %H:%M",
    ):
        try:
            return datetime.strptime(f"{date} {time}", fmt).replace(tzinfo=TZ)
        except ValueError:
            continue
    return None


def first_datetime(data, prefixes):
    for prefix in prefixes:
        value = parse_datetime(data, prefix)
        if value is not None:
            return value
    return None


def main():
    request = urllib.request.Request(
        URL,
        headers={"User-Agent": "FMO-LaMetric-Feed/1.1"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        root = ET.fromstring(response.read())

    now = datetime.now(TZ)
    flights = []

    for node in root.iter():
        if tag_name(node.tag) != "FLIGHT":
            continue

        data = values(node)
        kind = data.get("FTYP", "").upper()
        if kind not in ("A", "D"):
            continue

        status = data.get("REM_CODE", "").upper()
        if status in {"CNL", "CANCELLED", "CANCELED"}:
            continue

        # Arrival and departure records use different time fields.
        if kind == "A":
            planned = first_datetime(data, ("STA", "STD"))
            expected = first_datetime(data, ("ETA", "ETD"))
            actual = first_datetime(data, ("ATA", "ATD"))
            # If the feed says this arrival has actually occurred, skip it.
            if actual is not None or status == "ARR":
                continue
            city = (
                data.get("CITY")
                or data.get("CITY3")
                or data.get("VIA")
                or data.get("VIA3")
                or ""
            ).strip()
        else:
            planned = first_datetime(data, ("STD", "STA"))
            expected = first_datetime(data, ("ETD", "ETA"))
            actual = first_datetime(data, ("ATD", "ATA"))
            if actual is not None or status == "DEP":
                continue
            city = (
                data.get("CITY")
                or data.get("CITY3")
                or data.get("VIA")
                or data.get("VIA3")
                or ""
            ).strip()

        # Use expected time when supplied; otherwise fall back to planned time.
        when = expected or planned
        if when is None or when < now:
            continue

        number = data.get("FNR", "").strip()
        if not number or not city:
            continue

        delay_minutes = 0
        if planned is not None and expected is not None:
            delay_minutes = max(
                0, int((expected - planned).total_seconds() // 60)
            )

        flights.append({
            "kind": kind,
            "number": number,
            "city": " ".join(city.split()),
            "when": when,
            "delay_minutes": delay_minutes,
        })

    flights.sort(key=lambda flight: flight["when"])
    arrivals = [flight for flight in flights if flight["kind"] == "A"][:3]
    departures = [flight for flight in flights if flight["kind"] == "D"][:3]

    selected = arrivals + departures
    selected.sort(key=lambda flight: flight["when"])

    frames = []
    for flight in selected:
        label = "AN" if flight["kind"] == "A" else "AB"
        text = (
            f"{label} {flight['number']} {flight['city']} "
            f"{flight['when']:%H:%M}"
        )
        if flight["delay_minutes"] >= DELAY_THRESHOLD_MINUTES:
            text += f" +{flight['delay_minutes']}m"

        frames.append({"text": text, "duration": 6000})

    if not frames:
        frames = [{"text": "FMO: Keine kommenden Fluege", "duration": 6000}]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps({"frames": frames}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        f"Generated {OUT}: {len(arrivals)} arrivals, "
        f"{len(departures)} departures"
    )
    for frame in frames:
        print(" -", frame["text"])


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise
