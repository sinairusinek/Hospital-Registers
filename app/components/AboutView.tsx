
import React from 'react';
import { BookOpen, Users, Cog, ArrowRight } from 'lucide-react';
import { ViewType } from '../types';

interface AboutViewProps {
  recordCount: number;
  onEnter: (view: ViewType) => void;
}

// Placeholders. Each section is a slot waiting for its text; the headings and
// the order are the argument, the prose is not written yet.
const SECTIONS = [
  {
    icon: BookOpen,
    title: 'The registers',
    placeholder:
      'This is the place for a short introduction: what the Haifa Government Hospital admission registers are, the years they cover, what a single record holds, and why the series is worth reading as a whole.'
  },
  {
    icon: Users,
    title: 'Who made this',
    placeholder:
      'This is the place for the people and the institutions: who did the work, in what roles, under whose auspices, with what funding, and how the project should be cited.'
  },
  {
    icon: Cog,
    title: 'How it was made',
    placeholder:
      'This is the place for the method: how the pages became data, what was standardized and what was deliberately left as written, the privacy decisions taken over names and addresses, and where the limits of the dataset lie.'
  }
];

const AboutView: React.FC<AboutViewProps> = ({ recordCount, onEnter }) => (
  <div className="h-full overflow-y-auto custom-scrollbar bg-slate-50">
    <div className="max-w-3xl mx-auto px-8 py-16 space-y-12">
      <header className="space-y-4">
        <p className="text-[10px] font-bold text-indigo-600 uppercase tracking-[0.2em]">
          Haifa Government Hospital
        </p>
        <h1 className="text-4xl font-bold text-slate-900 tracking-tight">Admission Registers</h1>
        <p className="text-lg text-slate-500 leading-relaxed">
          This is the place for a one-paragraph statement of what this site is and what a
          visitor can do with it.
        </p>
        {recordCount > 0 && (
          <p className="text-sm text-slate-400 font-mono">{recordCount.toLocaleString()} admission records</p>
        )}
      </header>

      <div className="space-y-4">
        {SECTIONS.map(({ icon: Icon, title, placeholder }) => (
          <section key={title} className="bg-white border border-slate-200 rounded-2xl p-6 space-y-3">
            <h2 className="font-bold text-slate-800 flex items-center gap-2">
              <Icon size={18} className="text-indigo-500" /> {title}
            </h2>
            <p className="text-sm leading-relaxed text-slate-400 italic">{placeholder}</p>
          </section>
        ))}
      </div>

      <div className="flex flex-wrap gap-3">
        <button
          onClick={() => onEnter('browse')}
          className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-sm font-medium transition-colors"
        >
          Browse the records <ArrowRight size={16} />
        </button>
        <button
          onClick={() => onEnter('statistics')}
          className="flex items-center gap-2 px-5 py-2.5 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-xl text-sm font-medium transition-colors"
        >
          See the statistics <ArrowRight size={16} />
        </button>
      </div>
    </div>
  </div>
);

export default AboutView;
