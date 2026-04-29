# The Dominion List

An open-source database of the most influential Canadian founders building companies in America.

**[Browse the database](https://cfddb.vercel.app)** · **[Analytics](https://cfddb.vercel.app/analytics.html)** · **[Methodology](https://cfddb.vercel.app/methodology.html)**

## What is this?

The Dominion List tracks 430+ US-incorporated technology companies founded or co-founded by people with significant Canadian roots. The database includes funding history, valuations, founder profiles, institutional connections, and industry classification for each company.

The project exists to quantify the scale and impact of Canadian-born and Canadian-educated founders in the American technology ecosystem.

## Data

All data lives in `data/companies.json` — a single structured JSON file. Each entry contains:

- Company details (name, website, HQ, founding year, industry, stage, status)
- Founder profiles (name, role, bio, Canadian connection type, institution)
- Funding rounds (date, round type, amount, investors, valuations)

`data/metadata.json` tracks the database version and last update date.

See the [Methodology](https://cfddb.vercel.app/methodology.html) page for inclusion criteria, taxonomy definitions, data pipeline details, schema documentation, and known limitations.

## Running locally

This is a static site — no build step, no dependencies, no framework.

```bash
git clone https://github.com/antoinenivard/dominion-list.git
cd dominion-list

# Serve locally (any static server works)
python3 -m http.server 8000
# or
npx serve .
```

Open `http://localhost:8000` in your browser.

## Project structure

```
dominion-list/
  index.html          # Main database table with search, filter, sort
  analytics.html      # Interactive charts and data visualizations
  methodology.html    # How the database is built and maintained
  favicon.ico         # Site icon
  data/
    companies.json    # The database (single source of truth)
    metadata.json     # Version and update tracking
  .github/
    ISSUE_TEMPLATE/   # Templates for submitting companies and edits
```

## Contributing

We welcome contributions. The most common ways to help:

- **Submit a company** — open a [GitHub issue](https://github.com/antoinenivard/dominion-list/issues/new?template=submit-company.md) with the company details and a public source confirming the Canadian founder connection.
- **Suggest a correction** — open a [GitHub issue](https://github.com/antoinenivard/dominion-list/issues/new?template=suggest-edit.md) with the company name, what needs to change, and a source.
- **Edit the data directly** — fork the repo, edit `data/companies.json`, and open a pull request.

All submissions require at least one public source. See [CONTRIBUTING.md](CONTRIBUTING.md) for full guidelines.

## Citation

If you use The Dominion List in research, journalism, or analysis:

> Nivard, A. (2026). *The Dominion List: A Database of Canadian-Founded US Technology Companies.* Available at [cfddb.vercel.app](https://cfddb.vercel.app). Source: [github.com/antoinenivard/dominion-list](https://github.com/antoinenivard/dominion-list).

## License

Code and data are released under the [MIT License](LICENSE).

## Author

Built by [Antoine Nivard](https://antoinenivard.com) in San Francisco.
