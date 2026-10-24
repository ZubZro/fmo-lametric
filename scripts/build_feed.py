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
    return {tag_name(c.tag): (c.text or "").strip() for c in list(flight)}

def dt(v, prefix):
    date, time = v.get(prefix + "_DATE", ""), v.get(prefix + "_TIME", "")
    if not date or not time:
        return None
    for fmt in ("%d.%m.%Y %H:%M", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(date + " " + time, fmt).replace(tzinfo=TZ)
        except ValueError:
            pass
    return None

def main():
    req = urllib.request.Request(URL, headers={"User-Agent": "FMO-LaMetric-Feed/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        root = ET.fromstring(r.read())

    now = datetime.now(TZ)
    upcoming = []
    for node in root.iter():
        if tag_name(node.tag) != "FLIGHT":
            continue
        v = values(node)
        kind = v.get("FTYP", "").upper()
        if kind not in ("A", "D"):
            continue
        # FMO's ATD_TIME / completed status is used to exclude flights already operated.
        if v.get("ATD_TIME") or v.get("REM_CODE", "").upper() in {
            "ARR", "DEP", "CNL", "CANCELLED", "CANCELED"
        }:
            continue
        when = dt(v, "ETD") or dt(v, "STD")
        if when is None or when < now:
            continue
        number = v.get("FNR", "").strip()
        city = (v.get("CITY") or v.get("CITY3") or v.get("VIA") or v.get("VIA3") or "").strip()
        if number and city:
            upcoming.append({"kind": kind, "number": number, "city": " ".join(city.split()), "when": when})

    upcoming.sort(key=lambda x: x["when"])
    arrivals = [f for f in upcoming if f["kind"] == "A"][:3]
    departures = [f for f in upcoming if f["kind"] == "D"][:3]
    frames = []
    for label, group in (("AN", arrivals), ("AB", departures)):
        for f in group:
            frames.append({"text": f"{label} {f['number']} {f['city']} {f['when']:%H:%M}", "duration": 6000})
    if not frames:
        frames = [{"text": "FMO: Keine kommenden Fluege"}]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"frames": frames}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {OUT}: {len(arrivals)} arrivals, {len(departures)} departures")
    for f in frames:
        print(" -", f["text"])

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise
