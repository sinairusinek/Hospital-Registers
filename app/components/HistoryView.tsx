import React, { useState } from 'react';
import { ExternalLink, Loader2 } from 'lucide-react';
import WorkInProgress from './WorkInProgress';

/**
 * "Mountain Road to Bat Galim" — the institutional history, as a tab.
 *
 * The document is a self-contained HTML file with its own typography, source
 * drawer and contents rail, authored outside this app and copied verbatim into
 * public/. It is framed rather than ported: rewriting 366 KB of prose as React
 * would buy nothing and would fork the text away from the file that is also
 * published as an artifact and shared with colleagues.
 *
 * Like About and Timeline, it stands on its own file and so is readable before
 * — and without — the register TSV.
 */
const HistoryView: React.FC = () => {
  const [loaded, setLoaded] = useState(false);
  const src = `${import.meta.env.BASE_URL}hospital-history.html`;

  return (
    <div className="h-full flex flex-col bg-white">
      <WorkInProgress>
        a working draft. Its last section lists what is still unresolved, and
        several passages are marked open where the evidence does not yet settle
        the question.
      </WorkInProgress>
      <div className="flex items-center justify-between gap-4 px-4 py-2 border-b border-slate-200 bg-slate-50">
        <p className="text-xs text-slate-600">
          The institutional history, 1918–1948 — every citation opens the press
          article or archive file behind it.
        </p>
        <a
          href={src}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 text-xs font-medium text-indigo-600 hover:text-indigo-800 whitespace-nowrap"
        >
          Open in a new tab
          <ExternalLink size={13} />
        </a>
      </div>

      <div className="flex-1 relative">
        {!loaded && (
          <div className="absolute inset-0 flex items-center justify-center bg-white">
            <Loader2 className="animate-spin text-indigo-600" size={28} />
          </div>
        )}
        <iframe
          src={src}
          title="Mountain Road to Bat Galim — the institutional history of the Haifa Government Hospital"
          className="w-full h-full border-0"
          onLoad={() => setLoaded(true)}
        />
      </div>
    </div>
  );
};

export default HistoryView;
