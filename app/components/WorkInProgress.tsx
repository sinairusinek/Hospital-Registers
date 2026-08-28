import React from 'react';
import { AlertTriangle } from 'lucide-react';

/**
 * A standing notice that a view is unfinished.
 *
 * Both views it marks are genuinely provisional in different ways: Review
 * shows flags whose adjudication is still open, and the History is a draft
 * with a section of unresolved questions. Saying so where the reader is,
 * rather than in a footnote, is the honest option for a public site.
 */
const WorkInProgress: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div
    role="note"
    className="flex items-start gap-2 px-4 py-2 text-[11px] leading-snug
               text-amber-800 bg-amber-50 border-b border-amber-200"
  >
    <AlertTriangle size={13} className="mt-px shrink-0 text-amber-600" />
    <p>
      <span className="font-semibold uppercase tracking-wide">Work in progress</span>
      {' — '}
      {children}
    </p>
  </div>
);

export default WorkInProgress;
