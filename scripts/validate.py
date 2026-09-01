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


def at_commit(ref):
    """(metadata, company count) at a git ref, or None if unavailable."""
    import subprocess
    try:
        m = subprocess.run(["git", "show", f"{ref}:data/metadata.json"],
                           capture_output=True, text=True, check=True).stdout
        c = subprocess.run(["git", "show", f"{ref}:data/companies.json"],
                           capture_output=True, text=True, check=True).stdout
        return json.loads(m), len(json.loads(c))
    except Exception:
        return None


def parse(v):
    m = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", v or "")
    return tuple(int(x) for x in m.groups()) if m else None


def is_patch_bump(older, newer):
    """True when newer differs from older only by an increased patch digit."""
    a, b = parse(older), parse(newer)
    return bool(a and b and a[0] == b[0] and a[1] == b[1] and b[2] > a[2])


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

    # ── the same founder should look the same everywhere ──
    # A person appearing at two companies is one person; a photo or profile URL
    # on one record and not the other is a gap, not a difference.
    people = {}
    for c in companies:
        for f in c.get("founders", []):
            people.setdefault(f.get("name"), []).append((c.get("name"), f))
    for name, recs in people.items():
        if len(recs) < 2:
            continue
        for field in ("photo_url", "linkedin", "x_url"):
            vals = {(co, (f.get(field) or "")) for co, f in recs}
            distinct = {v for _, v in vals}
            if len(distinct) < 2:
                continue
            if "" in distinct and len(distinct) == 2:
                missing = [co for co, v in vals if not v]
                warn(f"{name}: {field} missing on {', '.join(sorted(missing))} but set elsewhere")
            else:
                warn(f"{name}: {field} differs across companies — {sorted(vals)}")

    # ── versioning rule ──
    # Adding entries requires a patch bump. The exception is a second batch on
    # the same day: if the previous commit was itself a patch bump carrying that
    # day's date, further additions ride along on it. A minor or major release
    # does NOT absorb the additions that follow it.
    prev = at_commit("HEAD~1")
    if prev:
        p_meta, p_count = prev
        added = len(companies) - p_count
        if added > 0 and p_meta.get("db_version") == ver:
            prev2 = at_commit("HEAD~2")
            covered = (
                prev2 is not None
                and is_patch_bump(prev2[0].get("db_version"), p_meta.get("db_version"))
                and p_meta.get("last_updated_date_display")
                == meta.get("last_updated_date_display")
            )
            if covered:
                print(f"note: {added} more entries on a day already covered by {ver}")
            else:
                err(
                    f"{added} entries added but db_version is still {ver} — bump the "
                    f"patch (the first addition after any release starts a new patch)"
                )

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
