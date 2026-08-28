
import React, { useState, useMemo } from 'react';
import { ListFilter, X } from 'lucide-react';
import { RegistryRecord, FilterState } from '../types';
import { facetValue, UNKNOWN } from '../facets';
import { matchesNonFacet, failingFacetColumns } from '../filtering';

interface FilterSidebarProps {
  data: RegistryRecord[];
  filterState: FilterState;
  setFilterState: React.Dispatch<React.SetStateAction<FilterState>>;
  hideRangeKeys?: string[]; // New prop to hide specific ranges
}

const FilterSidebar: React.FC<FilterSidebarProps> = ({ data, filterState, setFilterState, hideRangeKeys = [] }) => {
  const [activeModalFacet, setActiveModalFacet] = useState<string | null>(null);
  const [modalSearch, setModalSearch] = useState('');

  // The requested order: diagnosis, result, sex, religion, nationality, ward.
  // Aliases are tried in order: the published artifact's plain names first, the
  // consolidated TSV's names after, so an uploaded source file still facets.
  const facetTargets = [
    // The ICD-9 chapter leads, because it is the only level of the
    // classification a ten-value facet list can actually represent: the code
    // column holds 2,514 distinct values and its three-digit category 821,
    // against nineteen chapters. The specific diagnosis follows it, so
    // narrowing to one disease is still a click away.
    {
      label: 'Diagnosis (ICD-9 chapter)',
      internalKey: 'icd-9 chapter',
      aliases: ['icd9 chapter', 'icd-9 chapter']
    },
    {
      label: 'Diagnosis (specific)',
      internalKey: 'diagnosis',
      aliases: ['standardprimaryicd9names', 'standardprimaryicd9name', 'standardized diagnosis', 'primary diagnosis']
    },
    // Third, because it is the one facet that describes the register rather
    // than the patient: whether a diagnosis was written down at all, and if it
    // was, whether the classification reached it. Selecting "Not recorded"
    // gives the 729 admissions the diagnosis charts cannot describe.
    {
      label: 'Diagnosis recorded?',
      internalKey: 'diagnosis recording',
      aliases: ['diagnosis recording']
    },
    // Fourth, and also about the register rather than the patient: how often
    // these clerks wrote down the operation instead of the illness. "Procedure
    // only" is the case where nothing but the operation was recorded.
    { label: 'Procedure named?', internalKey: 'procedure', aliases: ['procedure'] },
    { label: 'Result', internalKey: 'result', aliases: ['standardized result', 'standardized_result', 'outcome'] },
    { label: 'Sex', internalKey: 'sex', aliases: ['gender'] },
    { label: 'Religion', internalKey: 'religion', aliases: ['standardized religion', 'standardized_religion'] },
    { label: 'Nationality', internalKey: 'nationality', aliases: ['standardnationality'] },
    { label: 'Ward', internalKey: 'ward', aliases: ['standardized ward'] }
  ];

  const rangeTargets = [
    { key: 'Age', label: 'Age', isDate: false, aliases: ['age'] },
    { key: 'Days in Hospital', label: 'Length of Stay', isDate: false, aliases: ['days in hospital', 'days in hospital (calc)'] },
    { key: 'Admission Date', label: 'Admission Date', isDate: true, aliases: ['admission date', 'admission date [iso]'] }
  ];

  const actualKeys = useMemo<{
    facets: Record<string, string>;
    ranges: Record<string, string>;
  }>(() => {
    if (data.length === 0) return { facets: {}, ranges: {} };
    const dataKeys = Object.keys(data[0]);
    
    const facets: Record<string, string> = {};
    facetTargets.forEach((target) => {
      // Alias order is the priority order: the standardized column must win over
      // the raw one, which sits earlier in the TSV.
      let found: string | undefined;
      for (const alias of [target.internalKey, ...(target.aliases || [])]) {
        found = dataKeys.find(k => k.toLowerCase().trim() === alias);
        if (found) break;
      }
      if (found) facets[target.label] = found;
    });

    const ranges: Record<string, string> = {};
    rangeTargets.forEach(target => {
      for (const alias of target.aliases) {
        const found = dataKeys.find(k => k.toLowerCase().trim() === alias);
        if (found) { ranges[target.key] = found; break; }
      }
    });

    return { facets, ranges };
  }, [data]);

  // Each facet is counted over the records the *other* filters leave standing,
  // so the lists narrow to each other: choose an ICD-9 chapter and the specific
  // diagnoses below it are the diagnoses of that chapter, with the counts they
  // have inside it. A facet is never narrowed by its own selection — otherwise
  // ticking one value would erase the alternatives beside it, and the list
  // could not be widened again.
  //
  // A row is therefore counted in a facet if it fails no facet at all (it is in
  // the current selection), or if the only facet it fails is that one.
  const facetsData = useMemo(() => {
    const displayed = Object.entries(actualKeys.facets) as [string, string][];
    const results: Record<string, Record<string, number>> = {};
    displayed.forEach(([displayName]) => { results[displayName] = {}; });

    data.forEach(row => {
      if (!matchesNonFacet(row, filterState)) return;
      const failing = failingFacetColumns(row, filterState, 2);
      if (failing.length > 1) return;
      const exempt = failing[0]; // undefined when the row is in the selection

      displayed.forEach(([displayName, actualKey]) => {
        if (exempt !== undefined && exempt !== actualKey) return;
        // Blanks are a finding, not noise: 186 admissions record no sex at all.
        // They are bucketed as Unknown rather than dropped, using the same rule
        // App.tsx applies when filtering, so the count and the filter agree.
        const val = facetValue(row[actualKey]);
        results[displayName][val] = (results[displayName][val] || 0) + 1;
      });
    });
    return results;
  }, [data, actualKeys, filterState]);

  // The values to offer for one facet: what the other filters leave, plus any
  // value already ticked, so a selection can always be undone even when the
  // rest of the filters have reduced it to nothing. Ticked values sort first,
  // so narrowing another facet cannot push a live selection out of the top ten.
  const facetOptions = (displayName: string, selectedValues: string[]): [string, number][] => {
    const counts = { ...(facetsData[displayName] || {}) };
    selectedValues.forEach(val => { if (!(val in counts)) counts[val] = 0; });
    return (Object.entries(counts) as [string, number][]).sort((a, b) => {
      const selA = selectedValues.includes(a[0]) ? 1 : 0;
      const selB = selectedValues.includes(b[0]) ? 1 : 0;
      if (selA !== selB) return selB - selA;
      return b[1] - a[1];
    });
  };

  const clearFacet = (displayName: string) => {
    const actualKey = actualKeys.facets[displayName];
    if (!actualKey) return;
    setFilterState(prev => ({ ...prev, facets: { ...prev.facets, [actualKey]: [] } }));
  };

  const toggleFacet = (displayName: string, value: string) => {
    const actualKey = actualKeys.facets[displayName];
    if (!actualKey) return;

    setFilterState(prev => {
      const current = prev.facets[actualKey] || [];
      const next = current.includes(value) 
        ? current.filter(v => v !== value) 
        : [...current, value];
      return { ...prev, facets: { ...prev.facets, [actualKey]: next } };
    });
  };

  const updateRange = (targetKey: string, type: 'min' | 'max', value: number) => {
    const actualKey = actualKeys.ranges[targetKey];
    if (!actualKey) return;

    setFilterState(prev => ({
      ...prev,
      ranges: {
        ...prev.ranges,
        [actualKey]: {
          ...prev.ranges[actualKey],
          [type === 'min' ? 'currentMin' : 'currentMax']: value
        }
      }
    }));
  };

  const formatDate = (timestamp: number) => {
    return new Date(timestamp).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
  };

  return (
    <>
      <aside className="w-72 bg-white border-r border-slate-200 overflow-y-auto shrink-0 flex flex-col p-4 space-y-8 h-full custom-scrollbar">
        <div className="flex items-center justify-between">
          <h3 className="font-bold text-slate-800 flex items-center gap-2 text-sm">
            <ListFilter size={16} className="text-indigo-600" />
            Registry Filters
          </h3>
          <button 
            onClick={() => setFilterState(prev => ({ ...prev, searchQuery: '', advancedSearch: [], facets: {} }))}
            className="text-[10px] text-indigo-600 hover:text-indigo-800 font-bold uppercase tracking-wider"
          >
            Reset
          </button>
        </div>

        {/* Said once, because it changes how every list below is read. */}
        <p className="-mt-6 text-[10px] leading-snug text-slate-400">
          Each list shows the values, and the counts, left by the other filters.
        </p>

        <div className="space-y-6">
          <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-[0.2em]">Numeric / Date Ranges</h4>
          {rangeTargets
            .filter(t => !hideRangeKeys.includes(t.key))
            .map(target => {
            const actualKey = actualKeys.ranges[target.key];
            const range = filterState.ranges[actualKey || ''];
            if (!range) return null;

            const displayMin = target.isDate ? formatDate(range.currentMin) : range.currentMin;
            const displayMax = target.isDate ? formatDate(range.currentMax) : range.currentMax;

            return (
              <div key={target.key} className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-xs font-semibold text-slate-700">{target.label}</span>
                  <span className="text-[9px] font-mono bg-slate-100 px-2 py-0.5 rounded text-slate-500 whitespace-nowrap">
                    {displayMin} - {displayMax}
                  </span>
                </div>
                <div className="flex flex-col gap-1">
                  <input type="range" min={range.min} max={range.max} value={range.currentMin} onChange={(e) => updateRange(target.key, 'min', Number(e.target.value))} className="w-full accent-indigo-600 h-1" />
                  <input type="range" min={range.min} max={range.max} value={range.currentMax} onChange={(e) => updateRange(target.key, 'max', Number(e.target.value))} className="w-full accent-indigo-600 h-1" />
                </div>
              </div>
            );
          })}
        </div>

        <div className="space-y-8">
          {facetTargets.map(target => {
            const displayName = target.label;
            const actualKey = actualKeys.facets[displayName];
            if (!actualKey) return null;

            const selectedValues = filterState.facets[actualKey] || [];
            const selectedCount = selectedValues.length;
            const allValues = facetOptions(displayName, selectedValues);
            // Show top 10 most frequent diagnoses or items to handle high cardinality
            const known = allValues.filter(([val]) => val !== UNKNOWN);
            const unknown = allValues.find(([val]) => val === UNKNOWN);
            // Unknown is pinned below the top 10 rather than competing with them:
            // for a facet like Diagnosis it would otherwise either dominate the
            // list or, for a sparse one, never surface at all.
            const topItems = unknown ? [...known.slice(0, 10), unknown] : known.slice(0, 10);

            return (
              <div key={displayName} className="space-y-3">
                <div className="flex justify-between items-center">
                  <h4 title={displayName} className="text-[10px] font-bold text-slate-400 uppercase tracking-[0.2em] truncate mr-2">{displayName}</h4>
                  {selectedCount > 0 && (
                    <button
                      onClick={() => clearFacet(displayName)}
                      title="Clear this filter"
                      className="bg-indigo-600 hover:bg-indigo-700 text-white text-[9px] px-1.5 py-0.5 rounded-full font-bold flex items-center gap-1 shrink-0"
                    >
                      {selectedCount}
                      <X size={9} strokeWidth={3} />
                    </button>
                  )}
                </div>
                <div className="space-y-1">
                  {allValues.length === 0 && (
                    <p className="text-[10px] text-slate-400 italic">No values in the current selection</p>
                  )}
                  {topItems.map(([val, count]) => (
                    <label key={val} className="flex items-center group cursor-pointer">
                      <input 
                        type="checkbox" 
                        className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 w-3.5 h-3.5" 
                        checked={selectedValues.includes(val)} 
                        onChange={() => toggleFacet(displayName, val)} 
                      />
                      <span title={val} className={`ml-2 text-xs group-hover:text-slate-900 truncate flex-1 ${val === UNKNOWN ? 'italic text-slate-400' : 'text-slate-600'}`}>{val}</span>
                      <span className="text-[9px] text-slate-400 font-mono">{count}</span>
                    </label>
                  ))}
                  {known.length > 10 && (
                    <button onClick={() => setActiveModalFacet(displayName)} className="text-[10px] text-indigo-600 font-bold hover:underline pt-1 flex items-center gap-1">
                      + View all {known.length}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </aside>

      {activeModalFacet && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-xl max-h-[80vh] flex flex-col overflow-hidden">
            <div className="p-6 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold text-slate-800">Select {activeModalFacet}</h3>
                <p className="text-xs text-slate-500">Counts are within the current selection.</p>
              </div>
              <button onClick={() => { setActiveModalFacet(null); setModalSearch(''); }}><X size={20} /></button>
            </div>
            <div className="p-4 bg-slate-50 border-b border-slate-100">
              <input type="text" placeholder={`Search in ${activeModalFacet}...`} className="w-full px-4 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-indigo-500" value={modalSearch} onChange={(e) => setModalSearch(e.target.value)} autoFocus />
            </div>
            <div className="flex-1 overflow-y-auto p-2 custom-scrollbar">
              {facetOptions(activeModalFacet, filterState.facets[actualKeys.facets[activeModalFacet] || ''] || [])
                .filter(([val]) => val.toLowerCase().includes(modalSearch.toLowerCase()))
                .map(([val, count]) => (
                  <label key={val} className={`flex items-center p-3 rounded-xl cursor-pointer transition-all ${(filterState.facets[actualKeys.facets[activeModalFacet] || ''] || []).includes(val) ? 'bg-indigo-50' : 'hover:bg-slate-50'}`}>
                    <input type="checkbox" className="rounded text-indigo-600 w-4 h-4" checked={(filterState.facets[actualKeys.facets[activeModalFacet] || ''] || []).includes(val)} onChange={() => toggleFacet(activeModalFacet, val)} />
                    <div className="ml-3 flex-1 min-w-0"><div title={val} className={`text-sm font-semibold truncate ${val === UNKNOWN ? 'italic text-slate-400' : 'text-slate-700'}`}>{val}</div><div className="text-[10px] text-slate-400 font-mono">{count.toLocaleString()} occurrences</div></div>
                  </label>
                ))}
            </div>
            <div className="p-4 border-t bg-slate-50 flex justify-end gap-3">
              <button onClick={() => { setActiveModalFacet(null); setModalSearch(''); }} className="px-6 py-2 bg-indigo-600 text-white rounded-xl text-xs font-bold">Done</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default FilterSidebar;
