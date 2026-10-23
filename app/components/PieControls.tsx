// The two controls both map tabs share: the switch between the pies' cuts,
// and the legend for whichever cut is showing.
import React from 'react';
import { PieChart } from 'lucide-react';
import { PieMode, PieScheme, PIE_MODES } from '../pieSchemes';

/** Which dimension the pies are cut by; sits under the basemap choice. */
export const PieModeSwitch: React.FC<{ mode: PieMode; onChange: (m: PieMode) => void }> = ({ mode, onChange }) => (
  <>
    <div className="flex items-center gap-1.5 px-2 pt-2.5 pb-1.5 mt-1.5 border-t border-slate-100 text-[10px] font-bold uppercase tracking-wider text-slate-400">
      <PieChart size={12} /> Pies show
    </div>
    <div className="flex flex-col gap-1">
      {PIE_MODES.map(m => (
        <button
          key={m.key}
          onClick={() => onChange(m.key)}
          className={`text-left px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${
            mode === m.key
              ? 'bg-indigo-50 text-indigo-700 border border-indigo-200'
              : 'text-slate-600 border border-transparent hover:bg-slate-50'
          }`}
        >
          {m.label}
        </button>
      ))}
    </div>
  </>
);

/** The slice colours, in the order they go round the pie. Chapter names are
 *  long, so that cut gets a single column. */
export const PieLegend: React.FC<{ scheme: PieScheme }> = ({ scheme }) => (
  <ul className={`mt-2 grid gap-x-3 gap-y-1 ${scheme.mode === 'chapter' ? 'grid-cols-1' : 'grid-cols-2'}`}>
    {scheme.keys.map(k => (
      <li key={k} className="flex items-center gap-1.5 text-[11px] text-slate-600">
        <span className="w-2.5 h-2.5 rounded-sm shrink-0" style={{ background: scheme.color(k) }} />
        {scheme.label(k)}
      </li>
    ))}
  </ul>
);
