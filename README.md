# Self-Driving Incidents Explorer

An open dataset of incidents in which a vehicle's automated-driving feature is claimed, questioned
or confirmed to be involved: crashes, near misses, police stops, people found asleep at the wheel,
and the court cases that follow. Provided by [CrimConsortium](https://crimconsortium.com).

- **Site:** https://crimconsortium-crimrxiv.github.io/self-driving-incidents/
- **Download:** [`data/self-driving-incidents.zip`](data/self-driving-incidents.zip) (everything), or single files in [`data/`](data)
- **Codebook:** [`CODEBOOK.md`](CODEBOOK.md)
- **Corrections and suggestions:** consortium@crimrxiv.com

The dataset covers Tesla for now. Other makers can be added in `config.yaml`.

## What happens each day

A scheduled job (`.github/workflows/refresh.yml`) runs once a day and does four things:

1. **Finds reports.** It searches Google News and Bing News for reports that name an
   automated-driving feature and describe something that happened.
2. **Builds cases.** Reports about the same event are grouped into one case. A later report about
   an earlier event (an arrest, a lawsuit, a verdict) is attached to that case.
3. **Codes each case.** A language model reads the reports
   and drafts the coded variables, a short neutral narrative, and a list of who said what.
4. **Rebuilds the site and the download files**, and saves them here only if something changed.

Nothing needs to be done by hand. To run it on demand, open the **Actions** tab, choose
**Refresh dataset**, and press **Run workflow**.

## Rules the coding follows

- The model may use only the reports attached to the case.
- Every coded value must come with a quotation. The program keeps the value only if that
  quotation is found word for word in the report. Values that fail are removed and counted.
- A mention of a feature is never treated as evidence that it was in use. Labels on the site say
  "mentioned in coverage". The variable `engagement_status` separates what an official source
  states from what a driver, lawyer or witness claims.
- Private individuals are not named in coded fields, narratives or claims.
- A case is published only after it is screened as one identifiable incident. Round-ups,
  statistics and product news are set aside and listed in `data/screened_out.csv` with the reason.
- Every record is marked "machine-coded, not yet reviewed" until a person has checked it.
- Article text is read at coding time and not stored. The repository keeps links, headlines,
  publisher summaries and short quotations.

## Files

| Path | What it is |
| --- | --- |
| `config.yaml` | All settings: search terms, makers covered, labels, coding limits |
| `pipeline/` | The program (collect, group, code, check, export) |
| `store/cases.json` | The working record of every case, including those waiting to be coded |
| `data/` | Public download files, rebuilt from the store |
| `cases/` | One web page per case |
| `index.html`, `search.html`, `about.html` | The site, rebuilt on every run |
| `tests/` | Checks that the rules above hold; they run before every refresh |

## Run it yourself

```
pip install -r requirements.txt
python -m unittest discover -s tests
python -m pipeline.run --no-code          # collect and rebuild, no coding
python -m pipeline.run --export-only      # rebuild pages and downloads from the store
```

Coding needs an API key in the `OPENAI_API_KEY` environment variable (on GitHub: a repository secret
with that name, under Settings, Secrets and variables, Actions). Without it the job still collects
reports and rebuilds the site; cases wait in the store until they can be coded. The model and the
per-run limit are set under `coder` in `config.yaml`.

Each record names its coder in the `coder` column. The first cases (November 2026) were drafted by
a different model in a one-off session using `python -m pipeline.handcode`, which runs drafted
answers through exactly the same checks as the daily job. They have not been reviewed by a person.

## Limits

This is not a count of all incidents, and counts are not rates. It holds only incidents that
reached published news in English and that the searches found. It does not establish fault or
cause. Machine coding makes mistakes; check the linked sources before relying on a record.

## Licence and citation

Data: CC BY 4.0. Code: MIT. See [`LICENSE`](LICENSE) and [`CITATION.cff`](CITATION.cff).

> CrimConsortium. *Self-Driving Incidents Explorer* [dataset]. https://crimconsortium-crimrxiv.github.io/self-driving-incidents/
