#!/usr/bin/env python3
"""Validate data/companies.json and data/metadata.json.

Run locally with:  python3 scripts/validate.py
CI runs this on every push; a non-zero exit fails the build.
"""
import json
import re
import sys
from collections import Counter

ROOT = "data/"
SECTORS = {"AI", "Enterprise", "Health", "Consumer", "Fintech", "Industrial", "Crypto"}
CONNECTIONS = {
    "education", "birthplace", "citizenship",
    "education_citizenship", "birthplace_education",
}
COMPANY_REQUIRED = [
    "id", "name", "website", "description", "hq_city", "hq_region", "hq_country",
    "industry", "stage", "status", "founding_year", "yc_batch", "icon_url",
    "founders", "funding_rounds", "capital_raised_usd", "capital_raised_display",
    "metadata",
]
FOUNDER_REQUIRED = [
    "name", "role", "linkedin", "x_url", "bio", "wikipedia_url",
    "canadian_connection_type", "canadian_institution", "canadian_institutions",
]
ROUND_REQUIRED = [
    "date", "round", "amount_usd", "amount_display", "valuation_usd",
    "valuation_display", "lead_investors", "other_investors", "source_urls", "notes",
]
ROUND_ARRAYS = ["lead_investors", "other_investors", "source_urls"]

errors, warnings = [], []


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


def main():
    with open(ROOT + "companies.json") as f:
        companies = json.load(f)
    with open(ROOT + "metadata.json") as f:
        meta = json.load(f)

    # ── metadata ──
    ver = meta.get("db_version", "")
    if not re.fullmatch(r"v\d+\.\d+\.\d+", ver):
        err(f"db_version {ver!r} is not vMAJOR.MINOR.PATCH")
    if meta.get("total_companies") != len(companies):
        err(
            f"total_companies is {meta.get('total_companies')} but companies.json "
            f"holds {len(companies)}"
        )

    # ── uniqueness ──
    for field in ("id", "name"):
        dupes = [v for v, n in Counter(str(c.get(field)) for c in companies).items() if n > 1]
        if dupes:
            err(f"duplicate {field}: {', '.join(sorted(dupes)[:10])}")

    # ── per company ──
    for c in companies:
        who = c.get("name", "<unnamed>")
        for f in COMPANY_REQUIRED:
            if f not in c:
                err(f"{who}: missing field {f}")

        # this is the check that would have caught the "United States" split
        if c.get("hq_country") != "US":
            err(f"{who}: hq_country is {c.get('hq_country')!r}, expected 'US'")

        if c.get("industry") not in SECTORS:
            err(f"{who}: industry {c.get('industry')!r} is not one of the 7 sectors")

        yr = c.get("founding_year")
        if not isinstance(yr, int) or not (1900 <= yr <= 2100):
            err(f"{who}: founding_year {yr!r} is not a plausible year")

        if not c.get("stage"):
            warn(f"{who}: stage is empty")

        for fo in c.get("founders", []):
            fname = fo.get("name", "<unnamed>")
            for f in FOUNDER_REQUIRED:
                if f not in fo:
                    err(f"{who} / {fname}: founder missing field {f}")
            ct = fo.get("canadian_connection_type")
            if ct not in CONNECTIONS:
                err(f"{who} / {fname}: canadian_connection_type {ct!r} is not recognised")
            if not isinstance(fo.get("canadian_institutions"), list):
                err(f"{who} / {fname}: canadian_institutions must be an array")

        for r in c.get("funding_rounds", []):
            label = r.get("round", "<no round>")
            for f in ROUND_REQUIRED:
                if f not in r:
                    err(f"{who} / {label}: round missing field {f}")
            for f in ROUND_ARRAYS:
                if f in r and not isinstance(r[f], list):
                    err(f"{who} / {label}: {f} must be an array, got {type(r[f]).__name__}")
            if r.get("valuation_usd") == 0:
                err(f"{who} / {label}: valuation_usd is 0 — use null for unknown")

    # ── report ──
    for w in warnings:
        print(f"warning: {w}")
    for e in errors:
        print(f"ERROR: {e}")
    print(
        f"\n{len(companies)} companies checked · {len(errors)} errors · "
        f"{len(warnings)} warnings · version {ver}"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
