#!/usr/bin/env python3
"""Fetch monthly state total nonfarm employment from the BLS API.

Writes data/state_employment.csv (state_fips, date, employment_thousands).

Run: python3 pipeline/fetch_bls.py
"""
from __future__ import annotations

import csv
import json
import os
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
URL = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
UA = {"User-Agent": "portfolio-research (set SEC_USER_AGENT)",
      "Content-Type": "application/json"}
FIPS = ["01", "02", "04", "05", "06", "08", "09", "10", "11", "12", "13", "15", "16",
        "17", "18", "19", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29",
        "30", "31", "32", "33", "34", "35", "36", "37", "38", "39", "40", "41", "42",
        "44", "45", "46", "47", "48", "49", "50", "51", "53", "54", "55", "56"]


def post(ids):
    body = json.dumps({"seriesid": ids, "startyear": "2016", "endyear": "2026"}).encode()
    req = urllib.request.Request(URL, data=body, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as fh:
        return json.load(fh)


def main():
    os.makedirs(DATA, exist_ok=True)
    rows = []
    for i in range(0, len(FIPS), 25):
        chunk = FIPS[i:i + 25]
        ids = [f"SMU{f}000000000000001" for f in chunk]
        resp = post(ids)
        if resp.get("status") != "REQUEST_SUCCEEDED":
            raise SystemExit(resp.get("message"))
        for s in resp["Results"]["series"]:
            fips = s["seriesID"][3:5]
            for d in s["data"]:
                if d["period"] == "M13":
                    continue
                try:
                    val = float(d["value"])
                except ValueError:
                    continue
                rows.append({"state_fips": fips,
                             "date": f"{d['year']}-{d['period'][1:]}-01",
                             "employment_thousands": val})
        time.sleep(0.4)
        print(f"batch {i//25 + 1} done, rows={len(rows)}", flush=True)

    rows.sort(key=lambda r: (r["state_fips"], r["date"]))
    with open(os.path.join(DATA, "state_employment.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["state_fips", "date", "employment_thousands"])
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} observations")


if __name__ == "__main__":
    main()
