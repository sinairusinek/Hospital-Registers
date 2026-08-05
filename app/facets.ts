// A single normalization rule for facet values, shared by the sidebar (which
// counts them) and App.tsx (which filters on them). If the two disagreed, a
// bucket could show a count that selecting it does not reproduce.
// The bucket is both the stored filter value and the visible label, so the
// sidebar, the charts and the filter state can never drift apart.
export const UNKNOWN = 'Not recorded';

export const facetValue = (raw: unknown): string => {
  if (raw === null || raw === undefined) return UNKNOWN;
  const val = String(raw).trim();
  if (val === '' || val === 'null' || val === 'undefined') return UNKNOWN;
  return val;
};
