
import React, { useState, useCallback, useMemo, useEffect } from 'react';
import { Upload, Table, BarChart3, FileSpreadsheet } from 'lucide-react';
import { RegistryRecord, ViewType, FilterState, ColumnConfig, RangeFilter } from './types';
import DataBrowser from './components/DataBrowser';
import StatisticsView from './components/StatisticsView';

declare const Papa: any;

const App: React.FC = () => {
  const [data, setData] = useState<RegistryRecord[]>([]);
  const [activeView, setActiveView] = useState<ViewType>('browse');
  const [isLoading, setIsLoading] = useState(false);
  const [columns, setColumns] = useState<ColumnConfig[]>([]);

  // Global Filter State
  const [filterState, setFilterState] = useState<FilterState>({
    searchQuery: '',
    advancedSearch: [],
    facets: {},
    ranges: {}
  });

  const rangeColumns = [
    { key: 'Age', label: 'Age', isDate: false },
    { key: 'Days in Hospital (Calc)', label: 'Length of Stay', isDate: false },
    { key: 'Admission Date [ISO]', label: 'Admission Date', isDate: true }
  ];

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsLoading(true);
    Papa.parse(file, {
      header: true,
      dynamicTyping: true,
      skipEmptyLines: true,
      complete: (results: any) => {
        const rawData = results.data;
        setData(rawData);
        
        if (rawData.length > 0) {
          const keys = Object.keys(rawData[0]);
          const defaultVisibleHeaders = [
            'notebook record id',
            'age',
            'sex',
            'standardized religion',
            'standardnationality',
            'standardprimaryicd9names',
            'standardprimaryicd9name', // Added singular version
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
            const actualKey = keys.find(k => k.toLowerCase().trim() === col.key.toLowerCase().trim());
            if (!actualKey) return;

            const values = rawData.map((r: any) => {
              const val = r[actualKey];
              if (isDateCol) {
                const d = new Date(val);
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
        setIsLoading(false);
      },
      error: (error: any) => {
        console.error('Parsing error:', error);
        setIsLoading(false);
        alert('Error parsing file. Please ensure it is a valid TSV.');
      }
    });
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
          const rowValue = String(row[col] || 'Unknown');
          if (!selectedValues.includes(rowValue)) return false;
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
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-indigo-600 rounded-xl flex items-center justify-center text-white shadow-lg shadow-indigo-100">
            <FileSpreadsheet size={24} />
          </div>
          <div>
            <h1 className="font-bold text-slate-800 tracking-tight">Hospital Registry</h1>
            <p className="text-xs text-slate-500 font-medium uppercase tracking-wider">Observer v1.0</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {data.length > 0 && (
            <div className="flex bg-slate-100 p-1 rounded-lg">
              <button
                onClick={() => setActiveView('browse')}
                className={`flex items-center gap-2 px-4 py-1.5 rounded-md text-sm font-medium transition-all ${
                  activeView === 'browse' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                <Table size={16} />
                Browser
              </button>
              <button
                onClick={() => setActiveView('statistics')}
                className={`flex items-center gap-2 px-4 py-1.5 rounded-md text-sm font-medium transition-all ${
                  activeView === 'statistics' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                <BarChart3 size={16} />
                Statistics
              </button>
            </div>
          )}
          <label className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium cursor-pointer transition-colors shadow-lg shadow-indigo-100">
            <Upload size={18} />
            {data.length > 0 ? 'Replace Dataset' : 'Upload TSV'}
            <input type="file" accept=".tsv,.txt,.csv" onChange={handleFileUpload} className="hidden" />
          </label>
        </div>
      </header>

      <main className="flex-1 overflow-hidden relative">
        {isLoading ? (
          <div className="absolute inset-0 bg-white/80 backdrop-blur-sm flex flex-col items-center justify-center z-50">
            <div className="w-16 h-16 border-4 border-indigo-100 border-t-indigo-600 rounded-full animate-spin mb-4"></div>
            <p className="text-slate-600 font-medium animate-pulse">Processing medical records...</p>
          </div>
        ) : data.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center p-8 text-center">
            <div className="w-24 h-24 bg-indigo-50 rounded-full flex items-center justify-center text-indigo-500 mb-6">
              <Upload size={48} />
            </div>
            <h2 className="text-2xl font-bold text-slate-800 mb-2">No data loaded yet</h2>
            <p className="text-slate-500 max-w-md mb-8">
              Upload your hospital registry TSV file to start exploring patterns, filtering diagnoses, and visualizing clinical statistics.
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
