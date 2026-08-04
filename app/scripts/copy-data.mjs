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
