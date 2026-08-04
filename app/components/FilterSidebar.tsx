
import React, { useState, useMemo } from 'react';
import { ListFilter, X } from 'lucide-react';
import { RegistryRecord, FilterState } from '../types';

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
    {
      label: 'Diagnosis',
      internalKey: 'diagnosis',
      aliases: ['standardprimaryicd9names', 'standardprimaryicd9name', 'standardized diagnosis', 'primary diagnosis']
    },
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

  const facetsData = useMemo(() => {
    const results: Record<string, Record<string, number>> = {};
    (Object.entries(actualKeys.facets) as [string, string][]).forEach(([displayName, actualKey]) => {
      const facetGroup: Record<string, number> = {};
      data.forEach(row => {
        const rawValue = row[actualKey];
        const val = String(rawValue ?? 'Unknown').trim();
        if (val && val !== 'null' && val !== 'undefined' && val !== 'Unknown') {
          facetGroup[val] = (facetGroup[val] || 0) + 1;
        }
      });
      results[displayName] = facetGroup;
    });
    return results;
  }, [data, actualKeys]);

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

            const allValues = (Object.entries(facetsData[displayName] || {}) as [string, number][]).sort((a, b) => b[1] - a[1]);
            // Show top 10 most frequent diagnoses or items to handle high cardinality
            const topItems = allValues.slice(0, 10);
            const selectedValues = filterState.facets[actualKey] || [];
            const selectedCount = selectedValues.length;

            return (
              <div key={displayName} className="space-y-3">
                <div className="flex justify-between items-center">
                  <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-[0.2em] truncate mr-2">{displayName}</h4>
                  {selectedCount > 0 && <span className="bg-indigo-600 text-white text-[9px] px-1.5 py-0.5 rounded-full font-bold">{selectedCount}</span>}
                </div>
                <div className="space-y-1">
                  {topItems.map(([val, count]) => (
                    <label key={val} className="flex items-center group cursor-pointer">
                      <input 
                        type="checkbox" 
                        className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 w-3.5 h-3.5" 
                        checked={selectedValues.includes(val)} 
                        onChange={() => toggleFacet(displayName, val)} 
                      />
                      <span className="ml-2 text-xs text-slate-600 group-hover:text-slate-900 truncate flex-1">{val}</span>
                      <span className="text-[9px] text-slate-400 font-mono">{count}</span>
                    </label>
                  ))}
                  {allValues.length > 10 && (
                    <button onClick={() => setActiveModalFacet(displayName)} className="text-[10px] text-indigo-600 font-bold hover:underline pt-1 flex items-center gap-1">
                      + View all {allValues.length}
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
              <div><h3 className="text-lg font-bold text-slate-800">Select {activeModalFacet}</h3></div>
              <button onClick={() => { setActiveModalFacet(null); setModalSearch(''); }}><X size={20} /></button>
            </div>
            <div className="p-4 bg-slate-50 border-b border-slate-100">
              <input type="text" placeholder={`Search in ${activeModalFacet}...`} className="w-full px-4 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-indigo-500" value={modalSearch} onChange={(e) => setModalSearch(e.target.value)} autoFocus />
            </div>
            <div className="flex-1 overflow-y-auto p-2 custom-scrollbar">
              {(Object.entries(facetsData[activeModalFacet] || {}) as [string, number][])
                .filter(([val]) => val.toLowerCase().includes(modalSearch.toLowerCase()))
                .sort((a, b) => b[1] - a[1])
                .map(([val, count]) => (
                  <label key={val} className={`flex items-center p-3 rounded-xl cursor-pointer transition-all ${(filterState.facets[actualKeys.facets[activeModalFacet] || ''] || []).includes(val) ? 'bg-indigo-50' : 'hover:bg-slate-50'}`}>
                    <input type="checkbox" className="rounded text-indigo-600 w-4 h-4" checked={(filterState.facets[actualKeys.facets[activeModalFacet] || ''] || []).includes(val)} onChange={() => toggleFacet(activeModalFacet, val)} />
                    <div className="ml-3 flex-1 min-w-0"><div className="text-sm font-semibold text-slate-700 truncate">{val}</div><div className="text-[10px] text-slate-400 font-mono">{count.toLocaleString()} occurrences</div></div>
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
