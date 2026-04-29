# Contributing to The Dominion List

Thank you for helping improve The Dominion List. This document explains how to submit new companies, suggest corrections, and contribute code changes.

## Submitting a new company

A company qualifies if it meets **all** of the following:

1. At least one founder or co-founder has a meaningful Canadian connection (born in Canada, attended a Canadian institution, or holds Canadian citizenship).
2. The company is incorporated or headquartered in the United States.
3. The company is a technology company or venture-backed startup that has raised venture capital, achieved meaningful revenue scale, or reached a significant valuation.

To submit a company, open a [GitHub issue](https://github.com/antoinenivard/dominion-list/issues/new?template=submit-company.md) using the "Submit a Company" template. Include at least one public source confirming the Canadian founder connection.

## Suggesting a correction

If you notice incorrect data (wrong founding year, outdated funding round, incorrect founder info), open a [GitHub issue](https://github.com/antoinenivard/dominion-list/issues/new?template=suggest-edit.md) using the "Suggest an Edit" template. Include a source URL for the correction.

## Editing the data directly

If you're comfortable with JSON and Git:

1. Fork this repository.
2. Edit `data/companies.json` — follow the existing entry format.
3. Make sure your changes are valid JSON (`python3 -m json.tool data/companies.json > /dev/null`).
4. Open a pull request with a brief description of what changed and why.
5. Include source URLs for any new data.

### Entry format

Each company entry must include at minimum:

- `name`, `website`, `description`
- `hq_city`, `hq_region`, `hq_country`
- `founding_year`, `industry`, `stage`, `status`
- At least one founder with `name`, `canadian_connection_type`, and `canadian_institution`

See the [Methodology page](https://cfddb.vercel.app/methodology.html) for the full schema documentation, industry taxonomy, and stage definitions.

## What we don't accept

- Companies headquartered outside the United States.
- Founders whose only Canadian connection is a brief visit, conference, or short-term work stint.
- Entries without at least one verifiable public source.
- Traditional businesses, franchises, or lifestyle businesses.

## Code of conduct

Be respectful and constructive. We're building a public resource — accuracy and good faith matter more than speed.
