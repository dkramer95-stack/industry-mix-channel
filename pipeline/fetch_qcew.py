#!/usr/bin/env python3
"""Fetch 2019 QCEW state area files (all industries, all ownerships).

Writes data/qcew_2019_state.csv with one row per state x industry x ownership.

Run: python3 pipeline/fetch_qcew.py
"""
from __future__ import annotations

import csv
import io
import os
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
UA = {"User-Agent": "portfolio-research (set SEC_USER_AGENT)"}
FIPS = ["01", "02", "04", "05", "06", "08", "09", "10", "11", "12", "13", "15", "16",
        "17", "18", "19", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29",
        "30", "31", "32", "33", "34", "35", "36", "37", "38", "39", "40", "41", "42",
        "44", "45", "46", "47", "48", "49", "50", "51", "53", "54", "55", "56"]


def get(url, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=90) as fh:
                return fh.read()
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("unreachable")


def main():
    os.makedirs(DATA, exist_ok=True)
    out_path = os.path.join(DATA, "qcew_2019_state.csv")
    rows = []
    for i, fips in enumerate(FIPS):
        area = f"{fips}000"
        url = f"https://data.bls.gov/cew/data/api/2019/a/area/{area}.csv"
        body = get(url).decode("utf-8", "ignore")
        reader = csv.DictReader(io.StringIO(body))
        for r in reader:
            if r.get("disclosure_code") == "N":
                continue
            try:
                emp = float(r["annual_avg_emplvl"])
            except (KeyError, ValueError):
                continue
            rows.append({
                "state_fips": fips,
                "area_fips": r["area_fips"],
                "own_code": r["own_code"],
                "industry_code": r["industry_code"],
                "agglvl_code": r["agglvl_code"],
                "annual_avg_emplvl": emp,
            })
        print(f"{i+1}/{len(FIPS)} {fips} rows={len(rows)}", flush=True)
        time.sleep(0.2)
    with open(out_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["state_fips", "area_fips", "own_code",
                                           "industry_code", "agglvl_code",
                                           "annual_avg_emplvl"])
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows -> {out_path}")


if __name__ == "__main__":
    main()
