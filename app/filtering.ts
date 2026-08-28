// One filtering rule, used twice: App.tsx selects the records with it, and the
// sidebar counts facet values with it. The sidebar needs to leave one facet out
// of the test at a time — that is what makes the filters responsive to each
// other — so the predicate is split into the part that never varies (search,
// advanced search, ranges) and the facet part, which is reported as a list of
// the columns a row fails rather than a yes/no.
import { RegistryRecord, FilterState, RangeFilter } from './types';
import { facetValue } from './facets';

// Search, advanced search and the range sliders: everything except the facets.
export const matchesNonFacet = (row: RegistryRecord, filterState: FilterState): boolean => {
  // 1. Global Search
  if (filterState.searchQuery !== '') {
    const needle = filterState.searchQuery.toLowerCase();
    const hit = Object.values(row).some(val => String(val).toLowerCase().includes(needle));
    if (!hit) return false;
  }

  // 2. Advanced Search (Specific Columns)
  for (const adv of filterState.advancedSearch) {
    if (adv.query && !String(row[adv.column] || '').toLowerCase().includes(adv.query.toLowerCase())) {
      return false;
    }
  }

  // 3. Range Filtering (Handles Numbers and Dates)
  for (const [col, range] of Object.entries(filterState.ranges) as [string, RangeFilter][]) {
    const rowVal = row[col];
    let numericVal: number;

    if (col.toLowerCase().includes('date')) {
      numericVal = new Date(String(rowVal)).getTime();
    } else {
      numericVal = Number(rowVal);
    }

    if (!isNaN(numericVal) && (numericVal < range.currentMin || numericVal > range.currentMax)) {
      return false;
    }
  }

  return true;
};

// The facet columns this row is excluded by. Stops after `limit` of them: a row
// that already fails two facets can never be counted under either, so counting
// further is wasted work on 30,000 rows.
export const failingFacetColumns = (
  row: RegistryRecord,
  filterState: FilterState,
  limit = Infinity
): string[] => {
  const failing: string[] = [];
  for (const [col, selectedValues] of Object.entries(filterState.facets) as [string, string[]][]) {
    if (selectedValues.length === 0) continue;
    if (!selectedValues.includes(facetValue(row[col]))) {
      failing.push(col);
      if (failing.length >= limit) break;
    }
  }
  return failing;
};

export const matchesFilters = (row: RegistryRecord, filterState: FilterState): boolean =>
  matchesNonFacet(row, filterState) && failingFacetColumns(row, filterState, 1).length === 0;
