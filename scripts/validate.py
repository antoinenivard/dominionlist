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
    "date", "round", "kind", "amount_usd", "amount_display", "valuation_usd",
    "valuation_display", "lead_investors", "other_investors", "source_urls", "notes",
]
ROUND_ARRAYS = ["lead_investors", "other_investors", "source_urls"]

# funding_rounds is really a financial-history timeline: it holds priced rounds
# alongside acquisitions, listings, wind-downs and market-cap marks, because the
# valuation logic on the site derives a company's current mark from the latest
# entry by date and needs the exits in the same sequence. That is deliberate.
# What is not acceptable is leaving consumers to guess which is which — the
# analytics page used to infer it from a label list plus a regex over the notes,
# and got it wrong in both directions. So every round carries an explicit kind,
# and a label may only ever mean one of the two.
#   funding — primary capital raised by the company from investors
#   event   — anything else: ownership changes, listings, liquidity for existing
#             holders, post-listing instruments, and pure valuation marks
EVENT_ROUNDS = {
    "Acquired", "Acquisition", "IPO", "SPAC", "IPO (SPAC)", "Direct Listing",
    "Spin-Off", "Wind Down", "Bankruptcy", "Restructuring", "Recapitalization",
    "Secondary", "Secondary Public Offering", "Tender Offer",
    "Post-IPO ATM", "Post-IPO Equity", "Post-IPO Debt", "Market Cap",
}
ROUND_KINDS = {"funding", "event"}

# status and stage are two independent axes and must stay that way. status is
# the outcome; stage is the financing stage reached, which stays true after an
# exit — Slack is Acquired and Series H. When they shared one vocabulary an exit
# overwrote the financing history, and 14 entries ended up asserting both at
# once (status Inactive with stage Seed, status Private with stage Acquired).
STATUSES = {"Private", "Public", "Acquired", "Inactive"}

# canadian_city is the founder's Canadian home town, not their university's
# city — 29 records prove the two come apart (Brockville, Markham, Sault Ste.
# Marie). Values were drifting to bare 'Toronto', to provinces, and once to
# 'Canada', so the shape is pinned here.
import re as _re
CITY_RE = _re.compile(
    r"[^,]+, (AB|BC|MB|NB|NL|NS|NT|NU|ON|PE|QC|SK|YT)")
STAGES = {
    "Pre-Seed", "Seed", "Series A", "Series B", "Series C", "Series D",
    "Series E", "Series F", "Series G", "Series H", "Series I", "Series J",
    "Series K", "Series L", "Growth", "Bootstrapped", "Private (PE)",
    "Early Stage",
}

# hq_region is the sidebar's HQ filter key, so it is grouped by exact string.
# Writing "California" where every other entry says "CA" therefore splits one
# state into two filter rows that each count a fraction of the companies —
# which is exactly what happened to California, New York and Pennsylvania.
# Codes only, and only real ones.
US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI",
    "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN",
    "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH",
    "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA",
    "WV", "WI", "WY", "PR",
}

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


def version_introduced_as_patch(ver, date_display, max_look=25):
    """Was `ver` introduced by a patch bump on `date_display`?

    Walks back until db_version differs from `ver`, then checks that the
    transition into `ver` was a patch bump and that the metadata date at that
    point matches today's. This has to scan rather than just look at HEAD~2:
    commits that change no entries (photo fixes, copy edits) sit between the
    patch bump and a later same-day addition, and an earlier version of this
    check wrongly failed those.
    """
    prev = None
    for i in range(1, max_look + 1):
        snap = at_commit(f"HEAD~{i}")
        if snap is None:
            # History ran out before a version change appeared. CI checks out
            # shallow (fetch-depth: 2), so this is the normal case there, not
            # evidence of a missing bump. Be lenient: a false build failure is
            # worse than a missed nudge, and the reviewer still sees the note.
            print(
                "note: git history too shallow to confirm the version bump "
                "(increase fetch-depth in the workflow to enforce this properly)"
            )
            return True
        meta_i = snap[0]
        if meta_i.get("db_version") != ver:
            return (
                is_patch_bump(meta_i.get("db_version"), ver)
                and prev is not None
                and prev.get("last_updated_date_display") == date_display
            )
        prev = meta_i
    return False


def parse(v):
    m = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", v or "")
    return tuple(int(x) for x in m.groups()) if m else None


def is_patch_bump(older, newer):
    """True when newer differs from older only by an increased patch digit."""
    a, b = parse(older), parse(newer)
    return bool(a and b and a[0] == b[0] and a[1] == b[1] and b[2] > a[2])


def check_photo_urls(companies):
    """Warn on photo_url values that no longer resolve.

    Hotlinked headshots rot: a company redesigns, a CDN path changes, a host
    starts blocking cross-origin requests. Without this the image silently
    falls back to initials and nobody notices. Warning-only and wrapped in a
    bare except — a flaky network must never fail the build. Set
    SKIP_PHOTO_CHECK=1 to skip it entirely.
    """
    import os
    if os.environ.get("SKIP_PHOTO_CHECK"):
        return
    try:
        import urllib.request
        from concurrent.futures import ThreadPoolExecutor
    except Exception:
        return

    urls = {}
    for c in companies:
        for f in c.get("founders", []):
            u = f.get("photo_url")
            if u:
                urls.setdefault(u, []).append(f"{f.get('name')} ({c.get('name')})")

    def probe(u):
        req = urllib.request.Request(
            u,
            method="GET",
            headers={
                # Some hosts 403 an absent or non-browser UA. Referer is set to
                # the live site so hotlink protection is exercised the same way
                # a real page view would exercise it.
                "User-Agent": "Mozilla/5.0 (compatible; dominionlist-linkcheck/1.0)",
                "Referer": "https://dominionlist.com/",
                "Accept": "image/*,*/*",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                ctype = (r.headers.get("Content-Type") or "").lower()
                if r.status >= 400:
                    return f"HTTP {r.status}"
                if "image" not in ctype:
                    return f"not an image (Content-Type: {ctype or 'none'})"
                return None
        except Exception as e:
            return type(e).__name__ + (f": {e}" if len(str(e)) < 80 else "")

    try:
        with ThreadPoolExecutor(max_workers=12) as ex:
            results = list(ex.map(probe, urls))
    except Exception:
        return

    for (u, who), problem in zip(urls.items(), results):
        if problem:
            warn(f"photo_url unreachable — {problem} — {', '.join(who)} — {u}")


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

        status = c.get("status")
        if status not in STATUSES:
            err(f"{who}: status {status!r} is not one of {sorted(STATUSES)}")

        stage = c.get("stage")
        if not stage:
            warn(f"{who}: stage is empty")
        elif stage not in STAGES:
            if stage in STATUSES:
                err(f"{who}: stage {stage!r} is an outcome, not a financing "
                    f"stage — it belongs in status, and stage should carry the "
                    f"round the company had reached")
            else:
                err(f"{who}: stage {stage!r} is not a recognised financing stage")

        # The outcome has to agree with the LAST terminal event on record, not
        # merely with the presence of one. Getaround and Sonder both went public
        # by SPAC and then wound down years later; an any-event rule called them
        # Public forever.
        terminal = {
            "Acquired": "Acquired", "Acquisition": "Acquired",
            "IPO": "Public", "SPAC": "Public", "IPO (SPAC)": "Public",
            "Direct Listing": "Public",
            "Wind Down": "Inactive", "Bankruptcy": "Inactive",
        }
        evs = [r for r in c.get("funding_rounds", [])
               if r.get("kind") == "event" and r.get("round") in terminal]
        if evs:
            evs.sort(key=lambda r: r.get("date") or "")
            last = evs[-1]
            want = terminal[last["round"]]
            if status != want:
                err(f"{who}: last terminal event is {last['round']!r} on "
                    f"{last.get('date')!r}, so status should be {want!r}, not {status!r}")

        icon = c.get("icon_url") or ""
        if "img.logo.dev" in icon and "fallback=404" not in icon:
            # Without this parameter logo.dev answers a miss with its own
            # monogram — a coloured letter tile in a different style from the
            # site's initials chip — so a company with no logo on file renders
            # as a stranger's design rather than falling through to our own
            # fallback. Two entries were doing exactly that when this was added.
            err(f"{who}: logo.dev icon_url must carry &fallback=404")

        region = c.get("hq_region")
        if not region:
            warn(f"{who}: hq_region is empty")
        elif region not in US_STATES:
            err(f"{who}: hq_region {region!r} is not a two-letter US state code")

        for fo in c.get("founders", []):
            fname = fo.get("name", "<unnamed>")
            for f in FOUNDER_REQUIRED:
                if f not in fo:
                    err(f"{who} / {fname}: founder missing field {f}")
            city = fo.get("canadian_city") or ""
            if city and not CITY_RE.fullmatch(city):
                err(f"{who} / {fname}: canadian_city {city!r} should read "
                    f"'City, PR' — it is a home town, not a province or a "
                    f"country, and not the city the university happens to be in")

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
            kind = r.get("kind")
            if kind not in ROUND_KINDS:
                err(f"{who} / {label}: kind {kind!r} must be one of {sorted(ROUND_KINDS)}")
            else:
                expected = "event" if r.get("round") in EVENT_ROUNDS else "funding"
                if kind != expected:
                    err(f"{who} / {label}: kind is {kind!r} but the round label "
                        f"{r.get('round')!r} is classified {expected!r}. Either the "
                        f"kind is wrong, or a new label needs adding to EVENT_ROUNDS.")

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
        # Profile URLs and photos were already checked here. The facts were not,
        # which is how Elon Musk ended up 'education' on three companies and
        # 'education_citizenship' on five, and how Riley Tomasek was 'education'
        # at one and 'birthplace' at the other. Where a person was born and
        # where they studied does not change between their companies.
        FOUNDER_FACTS = {"canadian_connection_type", "canadian_institution",
                         "canadian_city"}
        for field in ("photo_url", "linkedin", "x_url", "wikipedia_url",
                      "canadian_connection_type", "canadian_institution",
                      "canadian_city"):
            vals = {(co, (f.get(field) or "")) for co, f in recs}
            distinct = {v for _, v in vals}
            if len(distinct) < 2:
                continue
            if "" in distinct and len(distinct) == 2:
                missing = [co for co, v in vals if not v]
                warn(f"{name}: {field} missing on {', '.join(sorted(missing))} but set elsewhere")
            elif field in FOUNDER_FACTS:
                # Two different answers to a question with one answer. A URL can
                # lag; a birthplace cannot.
                err(f"{name}: {field} contradicts itself across companies — {sorted(vals)}")
            else:
                warn(f"{name}: {field} differs across companies — {sorted(vals)}")

        lists = {(co, tuple(f.get("canadian_institutions") or [])) for co, f in recs}
        if len({v for _, v in lists}) > 1:
            if () in {v for _, v in lists} and len({v for _, v in lists}) == 2:
                warn(f"{name}: canadian_institutions empty on some entries, set on others — {sorted(lists)}")
            else:
                err(f"{name}: canadian_institutions contradicts itself across companies — {sorted(lists)}")

    check_photo_urls(companies)

    # ── versioning rule ──
    # Adding entries requires a patch bump. The exception is a second batch on
    # the same day: if the previous commit was itself a patch bump carrying that
    # day's date, further additions ride along on it. A minor or major release
    # does NOT absorb the additions that follow it.
    # Baseline: HEAD~1 in CI, where HEAD is the commit being validated; HEAD when
    # run locally with uncommitted changes, where HEAD is still the last good state.
    # Always using HEAD~1 made every local pre-commit run report a phantom addition.
    import subprocess as _sp
    try:
        _dirty = bool(_sp.run(["git", "status", "--porcelain", "data/"],
                              capture_output=True, text=True, check=True).stdout.strip())
    except Exception:
        _dirty = False
    prev = at_commit("HEAD" if _dirty else "HEAD~1")
    if prev:
        p_meta, p_count = prev
        added = len(companies) - p_count
        if added > 0 and p_meta.get("db_version") == ver:
            covered = version_introduced_as_patch(
                ver, meta.get("last_updated_date_display")
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
