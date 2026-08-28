// Stages the published dataset into public/ so Vite ships it with the site.
// The artifact comes from pipeline/build.py; the consolidated TSV it is built
// from stays in data/public/ as the single source of truth.
import { mkdirSync, copyFileSync, existsSync } from 'fs';
import { dirname, resolve } from 'path';
import { fileURLToPath } from 'url';

const here = dirname(fileURLToPath(import.meta.url));
const src = resolve(here, '../../data/public/hospital-registers-normalized.tsv');
const dest = resolve(here, '../public/data/hospital-registers.tsv');

if (!existsSync(src)) {
  console.error(`Dataset not found at ${src}\nRun: python3 pipeline/build.py`);
  process.exit(1);
}

mkdirSync(dirname(dest), { recursive: true });
copyFileSync(src, dest);
console.log(`Staged dataset → ${dest}`);

// Notebook + page -> IIIF image service, so a record can be pointed at the
// scan of its own page. Built by pipeline/iiif_pages.py; optional, because a
// site without it falls back to the whole-notebook links.
const pagesSrc = resolve(here, '../../data/public/iiif-pages.tsv');
const pagesDest = resolve(here, '../public/data/iiif-pages.tsv');
if (existsSync(pagesSrc)) {
  copyFileSync(pagesSrc, pagesDest);
  console.log(`Staged IIIF page index → ${pagesDest}`);
}

// The Places panel joins each record's City onto the reviewed gazetteer
// decisions; the file is optional so the app still runs without it.
const decisionsSrc = resolve(here, '../../kimatch/city-kima-decisions.tsv');
const decisionsDest = resolve(here, '../public/data/city-kima-decisions.tsv');
if (existsSync(decisionsSrc)) {
  copyFileSync(decisionsSrc, decisionsDest);
  console.log(`Staged Kima decisions → ${decisionsDest}`);
}

// The Timeline view's four layers, assembled by pipeline/timeline_data.py.
// Optional: without it the view explains how to build it rather than failing.
const timelineSrc = resolve(here, '../../data/public/timeline.json');
const timelineDest = resolve(here, '../public/data/timeline.json');
if (existsSync(timelineSrc)) {
  copyFileSync(timelineSrc, timelineDest);
  console.log(`Staged timeline → ${timelineDest}`);
}

// The personnel strip: who MidEastMed places inside the hospital, built by
// pipeline/personnel_data.py. Optional, like the rest.
const personnelSrc = resolve(here, '../../data/public/personnel.json');
const personnelDest = resolve(here, '../public/data/personnel.json');
if (existsSync(personnelSrc)) {
  copyFileSync(personnelSrc, personnelDest);
  console.log(`Staged personnel → ${personnelDest}`);
}

// Coordinates for the reviewed City values, built by pipeline/place_coords.py.
// Optional: without it the Map view says how to build it rather than failing.
const coordsSrc = resolve(here, '../../data/public/place-coords.tsv');
const coordsDest = resolve(here, '../public/data/place-coords.tsv');
if (existsSync(coordsSrc)) {
  copyFileSync(coordsSrc, coordsDest);
  console.log(`Staged place coordinates → ${coordsDest}`);
}

// "Mountain Road to Bat Galim", the institutional history behind the History
// tab. Authored at paper/hospital-history.html, which is gitignored with the
// rest of the private drafts, so the *shipped* copy in public/ is the tracked
// one and CI builds from that. This step only refreshes it when the authored
// file is present — i.e. on the machine where it is written, never in CI.
const historySrc = resolve(here, '../../paper/hospital-history.html');
const historyDest = resolve(here, '../public/hospital-history.html');
if (existsSync(historySrc)) {
  copyFileSync(historySrc, historyDest);
  console.log(`Staged institutional history → ${historyDest}`);
}
