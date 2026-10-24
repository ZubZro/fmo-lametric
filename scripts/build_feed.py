#!/usr/bin/env python3

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

    formats = (
        "%d.%m.%Y %H:%M",
        "%Y-%m-%d %H:%M",
        "%d.%m.%y %H:%M",
    )

    for fmt in formats:
        try:
            return datetime.strptime(
                date + " " + time, fmt
            ).replace(tzinfo=TZ)
        except ValueError:
            continue

    return None


def main():
    request = urllib.request.Request(
        URL,
        headers={"User-Agent": "FMO-LaMetric-Feed/1.0"},
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

        # Bereits durchgeführte oder stornierte Flüge überspringen.
        if data.get("ATD_TIME"):
            continue

        if status in {
            "ARR", "DEP", "CNL", "CANCELLED", "CANCELED"
        }:
            continue

        # Zuerst die erwartete Zeit, sonst die Planzeit verwenden.
        when = (
            parse_datetime(data, "ETD")
            or parse_datetime(data, "STD")
        )

        if when is None or when < now:
            continue

        number = data.get("FNR", "").strip()

        city = (
            data.get("CITY")
            or data.get("CITY3")
            or data.get("VIA")
            or data.get("VIA3")
            or ""
        ).strip()

        if not number or not city:
            continue

        flights.append({
            "kind": kind,
            "number": number,
            "city": " ".join(city.split()),
            "when": when,
        })

    # Zunächst alle Flüge chronologisch sortieren.
    flights.sort(key=lambda flight: flight["when"])

    # Die jeweils drei zeitlich nächsten Ankünfte und Abflüge wählen.
    arrivals = [
        flight for flight in flights
        if flight["kind"] == "A"
    ][:3]

    departures = [
        flight for flight in flights
        if flight["kind"] == "D"
    ][:3]

    # Beide Gruppen zusammenführen und erneut gemeinsam sortieren.
    selected = arrivals + departures
    selected.sort(key=lambda flight: flight["when"])

    frames = []

    for flight in selected:
        label = "AN" if flight["kind"] == "A" else "AB"

        text = (
            f"{label} {flight['number']} "
            f"{flight['city']} {flight['when']:%H:%M}"
        )

        frames.append({
            "text": text,
            "duration": 6000,
        })

    if not frames:
        frames = [{
            "text": "FMO: Keine kommenden Fluege",
            "duration": 6000,
        }]

    OUT.parent.mkdir(parents=True, exist_ok=True)

    OUT.write_text(
        json.dumps(
            {"frames": frames},
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    print(
        f"Generated {OUT}: "
        f"{len(arrivals)} arrivals, "
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
