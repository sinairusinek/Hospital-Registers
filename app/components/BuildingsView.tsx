import React, { useState } from 'react';
import { ExternalLink, Loader2 } from 'lucide-react';
import WorkInProgress from './WorkInProgress';

/**
 * "The Buildings and the Wards" — the evidence dossier behind the History tab:
 * premises, bed strength, the designed building, the ward vocabulary, the
 * pavilions, and the documents. Framed like HistoryView, for the same reason:
 * it is a self-contained HTML file (paper/buildings-dossier.html, figures
 * injected by pipeline/buildings_figures.py) copied verbatim into public/.
 *
 * It stands on its own file, so it is readable before the register TSV loads.
 */
const BuildingsView: React.FC<{ hash?: string }> = ({ hash = '' }) => {
  const [loaded, setLoaded] = useState(false);
  const file = `${import.meta.env.BASE_URL}buildings-dossier.html`;
  const src = `${file}${hash ? `#${hash}` : ''}`;

  return (
    <div className="h-full flex flex-col bg-white">
      <WorkInProgress>
        an evidence file, not a narrative. It keeps what the register shows, what
        other sources say and what is only a candidate reading apart, and its
        last section lists what is still open.
      </WorkInProgress>
      <div className="flex items-center justify-between gap-4 px-4 py-2 border-b border-slate-200 bg-slate-50">
        <p className="text-xs text-slate-600">
          Where the hospital stood, its beds, its wards and pavilions, 1918–1948 —
          the documents, tables and register tests behind the History tab.
        </p>
        <a
          href={file}
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
          key={src}
          src={src}
          title="The Buildings and the Wards — evidence dossier on the Haifa Government Hospital's premises and wards"
          className="w-full h-full border-0"
          onLoad={() => setLoaded(true)}
        />
      </div>
    </div>
  );
};

export default BuildingsView;
