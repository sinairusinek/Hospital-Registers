import React, { useEffect, useState } from 'react';
import { ExternalLink, BookOpen, FileText } from 'lucide-react';

declare const Papa: any;

// notebook + page -> the IIIF image service for that page, built by
// pipeline/iiif_pages.py from the library's manifests and staged beside the
// dataset (see scripts/copy-data.mjs).
const PAGES_URL = `${import.meta.env.BASE_URL}data/iiif-pages.tsv`;

export interface PageScan {
  canvasIndex: number;
  label: string;
  width: number;
  height: number;
  service: string;
}

export type PageScanIndex = Map<string, PageScan>;

const key = (notebook: string | number, page: string | number) =>
  `${String(notebook).trim()}/${String(page).trim()}`;

/** The whole page, at a width that reads on screen and prints. */
export const pageImageUrl = (scan: PageScan, width = 2000) =>
  `${scan.service}/full/${width},/0/default.jpg`;

/**
 * A horizontal band of the page. The register rows are not addressed by the
 * manifest, so a caller that wants one row passes the band it computed; this
 * only formats the region syntax and clamps it to the canvas.
 */
export const pageRegionUrl = (
  scan: PageScan,
  region: { x: number; y: number; w: number; h: number },
  width = 1600
) => {
  const x = Math.max(0, Math.round(region.x));
  const y = Math.max(0, Math.round(region.y));
  const w = Math.min(scan.width - x, Math.round(region.w));
  const h = Math.min(scan.height - y, Math.round(region.h));
  return `${scan.service}/${x},${y},${w},${h}/${width},/0/default.jpg`;
};

// One fetch for the whole session, shared by every view that asks.
let pending: Promise<PageScanIndex> | null = null;

const loadPageScans = (): Promise<PageScanIndex> => {
  if (pending) return pending;
  pending = new Promise<PageScanIndex>(resolve => {
    Papa.parse(PAGES_URL, {
      download: true,
      header: true,
      skipEmptyLines: true,
      delimiter: '\t',
      complete: (results: any) => {
        const index: PageScanIndex = new Map();
        (results.data as Record<string, string>[]).forEach(row => {
          if (!row.image_service) return;
          index.set(key(row.Notebook_Number, row.Page_Number), {
            canvasIndex: Number(row.canvas_index),
            label: row.canvas_label,
            width: Number(row.width),
            height: Number(row.height),
            service: row.image_service
          });
        });
        resolve(index);
      },
      // The table is a convenience: a site that cannot fetch it still works,
      // it just falls back to the whole-notebook links.
      error: () => resolve(new Map())
    });
  });
  return pending;
};

export const usePageScans = (): PageScanIndex | null => {
  const [scans, setScans] = useState<PageScanIndex | null>(null);
  useEffect(() => {
    let live = true;
    loadPageScans().then(index => { if (live) setScans(index); });
    return () => { live = false; };
  }, []);
  return scans;
};

export const lookupScan = (
  scans: PageScanIndex | null,
  notebook: string,
  page: string
): PageScan | null => {
  if (!scans || !notebook || !page) return null;
  return scans.get(key(notebook, page)) || null;
};

/**
 * The link to the source for one record.
 *
 * Where the page is known, this goes to that page's image. The library's own
 * BookReader viewer cannot be opened at a page — its build never loads the
 * URL plugin, so `#page/n34` is read by nothing and no query parameter is
 * honoured server-side — so the page-exact link is the image itself, and the
 * viewer link stays alongside it for the volume as a whole.
 */
const ScanLink: React.FC<{
  scans: PageScanIndex | null;
  notebook: string;
  page: string;
  notebookUrl: string;
}> = ({ scans, notebook, page, notebookUrl }) => {
  const scan = lookupScan(scans, notebook, page);

  if (!scan && !notebookUrl) {
    return <span className="text-xs text-slate-400 italic">no scan for this notebook</span>;
  }

  return (
    <span className="flex items-center gap-4">
      {scan && (
        <a
          href={pageImageUrl(scan)}
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-1.5 text-xs font-bold text-indigo-600 hover:text-indigo-800 transition-colors"
        >
          <FileText size={13} /> Open page {page} <ExternalLink size={11} />
        </a>
      )}
      {notebookUrl && (
        <a
          href={notebookUrl}
          target="_blank"
          rel="noreferrer"
          className={`flex items-center gap-1.5 text-xs transition-colors ${
            scan
              ? 'text-slate-500 hover:text-slate-700'
              : 'font-bold text-indigo-600 hover:text-indigo-800'
          }`}
        >
          <BookOpen size={13} /> {scan ? 'Whole notebook' : 'Open the notebook scan'}
          <ExternalLink size={11} />
        </a>
      )}
    </span>
  );
};

export default ScanLink;
