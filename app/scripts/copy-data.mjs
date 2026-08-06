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
