
import React, { useState, useCallback, useMemo, useEffect } from 'react';
import { Upload, Table, BarChart3, Info } from 'lucide-react';
import { RegistryRecord, ViewType, FilterState, ColumnConfig, RangeFilter } from './types';
import { facetValue } from './facets';
import AboutView from './components/AboutView';
import DataBrowser from './components/DataBrowser';
import StatisticsView from './components/StatisticsView';

declare const Papa: any;

// The consolidated dataset ships with the site; see scripts/copy-data.mjs.
const DEFAULT_DATASET_URL = `${import.meta.env.BASE_URL}data/hospital-registers.tsv`;

// Column 45 of the source spreadsheets carries a corrupted header, an artifact of
// the original export. By position and content it is the standardized ICD-9 label
// for the primary diagnosis: it sits between origPrimICD9Name and Additional-ICD9,
// holds ICD-9 names, and is filled for 28,107 records against origPrimICD9Name's
// 18,971. Restoring the name also lets the diagnosis facet find it.
const HEADER_FIXES: Record<string, string> = {
  '<info@doctorsonly.co.i': 'standardPrimaryICD9Name'
};

// Three records carry a stray single letter in the Sex column — B, W and C, one
// each. They are transcription debris from neighbouring columns, not a recorded
// sex, so they are blanked at load time and join the Not recorded bucket in both
// the browser and the statistics view.
const KNOWN_SEX = ['male', 'female'];

const cleanSex = (rows: RegistryRecord[], keys: string[]) => {
  const sexKey = keys.find(k => ['sex', 'gender'].includes(k.toLowerCase().trim()));
  if (!sexKey) return;
  rows.forEach(row => {
    if (!KNOWN_SEX.includes(String(row[sexKey] ?? '').trim().toLowerCase())) {
      row[sexKey] = null;
    }
  });
};

const App: React.FC = () => {
  const [data, setData] = useState<RegistryRecord[]>([]);
  // About is the landing view: a visitor meets the project before the table.
  const [activeView, setActiveView] = useState<ViewType>('about');
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [columns, setColumns] = useState<ColumnConfig[]>([]);

  // Global Filter State
  const [filterState, setFilterState] = useState<FilterState>({
    searchQuery: '',
    advancedSearch: [],
    facets: {},
    ranges: {}
  });

  // First alias wins. The published artifact uses the plain names; the older
  // ones are kept so an uploaded copy of the consolidated TSV still works.
  const rangeColumns = [
    { key: 'Age', label: 'Age', isDate: false, aliases: ['age'] },
    { key: 'Days in Hospital', label: 'Length of Stay', isDate: false, aliases: ['days in hospital', 'days in hospital (calc)'] },
    { key: 'Admission Date', label: 'Admission Date', isDate: true, aliases: ['admission date', 'admission date [iso]'] }
  ];

  const parseSettings = {
    header: true,
    dynamicTyping: true,
    skipEmptyLines: true,
    delimiter: '\t',
    // The registers contain bare double quotes (inches, gershayim). Left to its
    // default quote handling PapaParse swallows them and silently merges rows —
    // 19,718 records instead of 29,880. Disabling quoting parses all of them.
    quoteChar: '',
    transformHeader: (h: string) => HEADER_FIXES[h.trim()] || h.trim()
  };

  const parseInto = (source: File | string, isUrl: boolean) => {
    setIsLoading(true);
    setLoadError(null);
    Papa.parse(source, {
      ...parseSettings,
      download: isUrl,
      complete: (results: any) => {
        // A repeated header line survives inside the source spreadsheets; drop it.
        // Needs a high threshold: legitimate records carry Ward = "Ward" and
        // Rate = "Rate", so a single self-matching field is not enough.
        const rawData = (results.data as RegistryRecord[]).filter(
          row => Object.entries(row).filter(([k, v]) => v === k).length < 5
        );

        if (rawData.length > 0) {
          const keys = Object.keys(rawData[0]);
          cleanSex(rawData, keys);
          // The cleaned columns carry the plain names in the published artifact,
          // so those are what the table shows by default. The verbatim columns
          // ("Nationality as written") are one click away under Columns.
          const defaultVisibleHeaders = [
            'notebook record id',
            'age',
            'sex',
            'religion',
            'nationality',
            'diagnosis',
            'admission date',
            'days in hospital',
            'result',
            // Consolidated-TSV names, for an uploaded copy of the source file.
            'standardized religion',
            'standardnationality',
            'standardprimaryicd9name',
            'admission date [iso]',
            'days in hospital (calc)',
            'standardized result'
          ];

          setColumns(keys.map(key => ({
            key,
            label: key,
            visible: defaultVisibleHeaders.includes(key.toLowerCase().trim())
          })));

          // Initialize Ranges
          const newRanges: Record<string, RangeFilter> = {};
          rangeColumns.forEach(col => {
            const isDateCol = col.isDate;
            let actualKey: string | undefined;
            for (const alias of col.aliases) {
              actualKey = keys.find(k => k.toLowerCase().trim() === alias);
              if (actualKey) break;
            }
            if (!actualKey) return;

            const values = rawData.map((r: any) => {
              const val = r[actualKey];
              if (isDateCol) {
                // Only trust ISO-shaped strings: a stray 0 would otherwise become
                // 1970 and stretch the slider past the end of the registers.
                if (!/^\d{4}-\d{2}-\d{2}/.test(String(val))) return null;
                const d = new Date(String(val));
                return isNaN(d.getTime()) ? null : d.getTime();
              }
              return typeof val === 'number' ? val : null;
            }).filter((v: any) => v !== null);

            if (values.length > 0) {
              const min = Math.min(...values);
              const max = Math.max(...values);
              newRanges[actualKey] = { min, max, currentMin: min, currentMax: max };
            }
          });

          setFilterState({
            searchQuery: '',
            advancedSearch: [],
            facets: {},
            ranges: newRanges
          });
        }
        // Set after cleaning, so no view ever renders the raw values.
        setData(rawData);
        setIsLoading(false);
      },
      error: (error: any) => {
        console.error('Parsing error:', error);
        setIsLoading(false);
        setLoadError(
          isUrl
            ? 'Could not load the bundled dataset. You can upload a TSV instead.'
            : 'Error parsing file. Please ensure it is a valid TSV.'
        );
      }
    });
  };

  // Load the bundled dataset on first paint; the upload button replaces it.
  useEffect(() => {
    parseInto(DEFAULT_DATASET_URL, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) parseInto(file, false);
  };

  // Central Filtering Logic
  const filteredData = useMemo(() => {
    return data.filter(row => {
      // 1. Global Search
      const matchesGlobal = filterState.searchQuery === '' || 
        Object.values(row).some(val => 
          String(val).toLowerCase().includes(filterState.searchQuery.toLowerCase())
        );
      if (!matchesGlobal) return false;

      // 2. Advanced Search (Specific Columns)
      for (const adv of filterState.advancedSearch) {
        if (adv.query && !String(row[adv.column] || '').toLowerCase().includes(adv.query.toLowerCase())) {
          return false;
        }
      }

      // 3. Facet Filtering
      for (const [col, selectedValues] of Object.entries(filterState.facets) as [string, string[]][]) {
        if (selectedValues.length > 0) {
          if (!selectedValues.includes(facetValue(row[col]))) return false;
        }
      }

      // 4. Range Filtering (Handles Numbers and Dates)
      for (const [col, range] of Object.entries(filterState.ranges) as [string, RangeFilter][]) {
        const rowVal = row[col];
        let numericVal: number;

        if (col.toLowerCase().includes('date')) {
          const d = new Date(String(rowVal));
          numericVal = d.getTime();
        } else {
          numericVal = Number(rowVal);
        }

        if (!isNaN(numericVal) && (numericVal < range.currentMin || numericVal > range.currentMax)) {
          return false;
        }
      }

      return true;
    });
  }, [data, filterState]);

  const toggleColumn = useCallback((key: string) => {
    setColumns(prev => prev.map(col => 
      col.key === key ? { ...col, visible: !col.visible } : col
    ));
  }, []);

  const visibleColumns = useMemo(() => columns.filter(c => c.visible), [columns]);

  return (
    <div className="flex flex-col h-screen bg-slate-50">
      <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-6 shrink-0 z-20">
        <div className="flex items-center gap-4">
          <img
            src={`${import.meta.env.BASE_URL}elijah-lab.png`}
            alt="eLijah-Lab: an Incubator for Digital Humanities, University of Haifa"
            className="h-9 w-auto shrink-0"
          />
          <div className="hidden sm:block h-9 w-px bg-slate-200" aria-hidden="true"></div>
          <div className="hidden sm:block">
            <h1 className="font-bold text-slate-800 tracking-tight">Hospital Registry</h1>
            <p className="text-xs text-slate-500 font-medium uppercase tracking-wider">Observer v1.0</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* About stands on its own text, so it is reachable while the dataset
              is still loading; the two data views are not. */}
          <div className="flex bg-slate-100 p-1 rounded-lg">
              <button
                onClick={() => setActiveView('about')}
                className={`flex items-center gap-2 px-4 py-1.5 rounded-md text-sm font-medium transition-all ${
                  activeView === 'about' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                <Info size={16} />
                About
              </button>
              <button
                onClick={() => setActiveView('browse')}
                disabled={data.length === 0}
                className={`flex items-center gap-2 px-4 py-1.5 rounded-md text-sm font-medium transition-all disabled:opacity-40 disabled:cursor-not-allowed ${
                  activeView === 'browse' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                <Table size={16} />
                Browser
              </button>
              <button
                onClick={() => setActiveView('statistics')}
                disabled={data.length === 0}
                className={`flex items-center gap-2 px-4 py-1.5 rounded-md text-sm font-medium transition-all disabled:opacity-40 disabled:cursor-not-allowed ${
                  activeView === 'statistics' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                <BarChart3 size={16} />
                Statistics
              </button>
          </div>
          <label className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium cursor-pointer transition-colors shadow-lg shadow-indigo-100">
            <Upload size={18} />
            {data.length > 0 ? 'Replace Dataset' : 'Upload TSV'}
            <input type="file" accept=".tsv,.txt,.csv" onChange={handleFileUpload} className="hidden" />
          </label>
        </div>
      </header>

      <main className="flex-1 overflow-hidden relative">
        {activeView === 'about' ? (
          <AboutView recordCount={data.length} onEnter={setActiveView} />
        ) : isLoading ? (
          <div className="absolute inset-0 bg-white/80 backdrop-blur-sm flex flex-col items-center justify-center z-50">
            <div className="w-16 h-16 border-4 border-indigo-100 border-t-indigo-600 rounded-full animate-spin mb-4"></div>
            <p className="text-slate-600 font-medium animate-pulse">Loading 29,880 admission records...</p>
          </div>
        ) : data.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center p-8 text-center">
            <div className="w-24 h-24 bg-indigo-50 rounded-full flex items-center justify-center text-indigo-500 mb-6">
              <Upload size={48} />
            </div>
            <h2 className="text-2xl font-bold text-slate-800 mb-2">No data loaded</h2>
            <p className="text-slate-500 max-w-md mb-8">
              {loadError || 'Upload a hospital registry TSV to start exploring patterns, filtering diagnoses, and visualizing clinical statistics.'}
            </p>
          </div>
        ) : (
          <div className="h-full flex">
            {activeView === 'browse' ? (
              <DataBrowser 
                data={data}
                filteredData={filteredData}
                filterState={filterState}
                setFilterState={setFilterState}
                columns={columns} 
                visibleColumns={visibleColumns} 
                onToggleColumn={toggleColumn}
              />
            ) : (
              <StatisticsView 
                fullData={data} 
                data={filteredData} 
                filterState={filterState} 
                setFilterState={setFilterState} 
              />
            )}
          </div>
        )}
      </main>
    </div>
  );
};

export default App;
