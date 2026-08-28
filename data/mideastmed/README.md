# MidEastMed — Government Hospital, Haifa (entity 60387)

Scraped 2026-08-28 from https://www.mideastmed.org/entity/60387/institution

MidEastMed is Liat Kozma's ERC project database ("A Regional History of Medicine
in the Middle East", HUJI), covering c. 1830–1960. Site content is licensed
CC-BY 4.0 (footer also shows CC BY-NC-SA on some pages — check before republishing).

The institution record: "Government Hospital, Haifa", subordinate to the
Department of Health, Jerusalem; city Haifa; service character Hospital;
ownership Governmental. This is OUR hospital.

## Files

- `mem_haifa_govhosp_staff.tsv` — the 54 activities recorded AT this hospital
  (matches the site's own "54 records found"), 48 unique people, one row per
  activity, with profession/religion/birth backfilled from the person records.
  **Start here.**
- `mem_people.tsv` — the 48 people, one row each: Latin + Arabic name forms,
  birth/death years, profession, city of birth, religion, photo URL.
- `mem_activities.tsv` — all 242 activities across these people's ENTIRE
  careers (53 other institutions), with per-activity source citations. This is
  where the prosopography lives: where they trained before Haifa, where they
  went after.
- `mem_bibrefs.tsv` — 61 person-level bibliographic references.
- `mideastmed_haifa_govhosp.json` — full nested records, superset of the TSVs.
- `scrape_acts.py`, `parse_people.py` — the scrapers, for re-running or for
  pointing at another institution (change the entity id).

## Method

Person pages are `/node/<id>`; the institution listing takes `?items_per_page=All`.
Fields are marked by `title="..."` attributes on spans, so parsing is stable.
There is no API and no bulk export. Requests were throttled at 0.6s.

## Caveats

- Religion is unrecorded for 37 of 48 people — the site-wide facet has it blank
  for 9,317 of 10,437, so absence means "not recorded", never "unknown to us".
- Activity years are single years (a mention date, e.g. an Official Gazette
  issue), NOT service spans. 51 of 54 are dated; range 1922–1948.
- "Study" (17) means the hospital's nursing/midwifery school — see
  project_govhosp_institution memory. "Work" is 37.
