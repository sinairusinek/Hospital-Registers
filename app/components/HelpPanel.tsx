
import React, { useState } from 'react';
import { HelpCircle, X } from 'lucide-react';

export interface HelpSection {
  heading: string;
  body: React.ReactNode;
}

interface HelpPanelProps {
  title: string;
  sections: HelpSection[];
  // Distinct per view, so folding the browser's panel does not fold the
  // statistics one. The choice survives a reload.
  storageKey: string;
}

const HelpPanel: React.FC<HelpPanelProps> = ({ title, sections, storageKey }) => {
  const [open, setOpen] = useState(() => {
    try {
      return localStorage.getItem(storageKey) !== 'closed';
    } catch {
      return true;
    }
  });

  const setOpenPersisted = (next: boolean) => {
    setOpen(next);
    try {
      localStorage.setItem(storageKey, next ? 'open' : 'closed');
    } catch {
      // A blocked localStorage only costs the panel its memory between visits.
    }
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpenPersisted(true)}
        title={title}
        className="shrink-0 w-10 border-l border-slate-200 bg-white hover:bg-slate-50 flex flex-col items-center gap-3 py-4 text-slate-400 hover:text-indigo-600 transition-colors"
      >
        <HelpCircle size={18} />
        <span className="text-[10px] font-bold uppercase tracking-[0.2em] [writing-mode:vertical-rl]">{title}</span>
      </button>
    );
  }

  return (
    <aside className="shrink-0 w-72 border-l border-slate-200 bg-white overflow-y-auto custom-scrollbar">
      <div className="sticky top-0 bg-white/95 backdrop-blur-sm border-b border-slate-100 px-5 py-4 flex items-center justify-between">
        <h3 className="text-[10px] font-bold text-slate-400 uppercase tracking-[0.2em] flex items-center gap-2">
          <HelpCircle size={14} /> {title}
        </h3>
        <button onClick={() => setOpenPersisted(false)} className="text-slate-400 hover:text-slate-700" title="Fold">
          <X size={16} />
        </button>
      </div>
      <div className="px-5 py-4 space-y-5">
        {sections.map(section => (
          <section key={section.heading} className="space-y-1.5">
            <h4 className="text-xs font-bold text-slate-800">{section.heading}</h4>
            <div className="text-xs leading-relaxed text-slate-600 space-y-2">{section.body}</div>
          </section>
        ))}
      </div>
    </aside>
  );
};

export default HelpPanel;
