
import React, { useMemo, useState, useEffect, useCallback } from 'react';
import { 
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, 
  PieChart, Pie, Cell, AreaChart, Area, Legend, Brush, BarChart, Bar
} from 'recharts';
import { GoogleGenAI } from "@google/genai";
import { TrendingUp, Users, MapPin, HeartPulse, Globe, CheckCircle2, Sparkles, BrainCircuit, Calendar, Baby, Timer, RotateCcw } from 'lucide-react';
import { RegistryRecord, FilterState } from '../types';
import FilterSidebar from './FilterSidebar';

interface StatisticsViewProps {
  fullData: RegistryRecord[];
  data: RegistryRecord[];
  filterState: FilterState;
  setFilterState: React.Dispatch<React.SetStateAction<FilterState>>;
}

const COLORS = ['#4f46e5', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#3b82f6', '#f43f5e', '#84cc16'];

const StatisticsView: React.FC<StatisticsViewProps> = ({ fullData, data, filterState, setFilterState }) => {
  const [aiInsight, setAiInsight] = useState<string>('');
  const [isGenerating, setIsGenerating] = useState(false);
  // The site is static and public, so no key can be baked into the bundle.
  // Visitors supply their own; it stays in this browser only.
  const [apiKey, setApiKey] = useState<string>(() => localStorage.getItem('gemini_api_key') || '');

  // Robust key mapping
  const actualKeys = useMemo(() => {
    if (fullData.length === 0) return {};
    const dataKeys = Object.keys(fullData[0]);
    const targets = [
      // Plain names first — those are the cleaned columns in the published
      // artifact — then the consolidated TSV's names as fallback.
      { id: 'Sex', aliases: ['sex', 'gender'] },
      { id: 'Result', aliases: ['result', 'standardized result', 'outcome', 'standardized_result'] },
      { id: 'Religion', aliases: ['religion', 'standardized religion', 'standardized_religion'] },
      { id: 'Diagnosis', aliases: ['diagnosis', 'standardprimaryicd9names', 'standardprimaryicd9name', 'standardized diagnosis', 'primary diagnosis'] },
      { id: 'Admission Date', aliases: ['admission date', 'admission date [iso]', 'date'] },
      { id: 'City', aliases: ['city', 'town', 'residence'] },
      { id: 'Nationality', aliases: ['nationality', 'standardnationality', 'standard_nationality'] },
      { id: 'Age', aliases: ['age'] },
      { id: 'Stay', aliases: ['days in hospital', 'days in hospital (calc)', 'length of stay', 'stay duration'] }
    ];
    const mapping: Record<string, string> = {};
    targets.forEach(target => {
      // Walk the aliases in order and take the first that exists, rather than
      // scanning the columns: the raw `Nationality` sits before
      // `StandardNationality` in the TSV and would otherwise win.
      let found: string | undefined;
      for (const alias of [...target.aliases, target.id.toLowerCase()]) {
        found = dataKeys.find(k => k.toLowerCase().trim() === alias);
        if (found) break;
      }
      if (found) mapping[target.id] = found;
    });
    return mapping;
  }, [fullData]);

  const timelineStats = useMemo(() => {
    const admissionTimeline: Record<string, number> = {};
    const dateKey = actualKeys['Admission Date'];
    if (!dateKey) return [];

    fullData.forEach(row => {
      const date = String(row[dateKey] || '');
      if (date && date.includes('-')) {
        const parts = date.split('-');
        if (parts.length >= 2) {
          const key = `${parts[0]}-${parts[1]}`;
          admissionTimeline[key] = (admissionTimeline[key] || 0) + 1;
        }
      }
    });

    return Object.entries(admissionTimeline)
      .map(([name, value]) => {
        const filteredCount = data.filter(row => String(row[dateKey] || '').startsWith(name)).length;
        return { name, total: value, value: filteredCount };
      })
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [fullData, data, actualKeys]);

  const stats = useMemo(() => {
    const distributions: Record<string, Record<string, number>> = {
      sex: {}, result: {}, religion: {}, city: {}, nationality: {}, diagnosis: {}, age: {}, stay: {}
    };

    data.forEach(row => {
      const sex = String((actualKeys['Sex'] && row[actualKeys['Sex']]) || 'Not Specified');
      distributions.sex[sex] = (distributions.sex[sex] || 0) + 1;

      const res = String((actualKeys['Result'] && row[actualKeys['Result']]) || 'Unknown');
      distributions.result[res] = (distributions.result[res] || 0) + 1;

      const rel = String((actualKeys['Religion'] && row[actualKeys['Religion']]) || 'Unknown');
      distributions.religion[rel] = (distributions.religion[rel] || 0) + 1;

      const city = String((actualKeys['City'] && row[actualKeys['City']]) || 'Unknown');
      distributions.city[city] = (distributions.city[city] || 0) + 1;

      const nat = String((actualKeys['Nationality'] && row[actualKeys['Nationality']]) || 'Unknown');
      distributions.nationality[nat] = (distributions.nationality[nat] || 0) + 1;

      const diagRaw = (actualKeys['Diagnosis'] && row[actualKeys['Diagnosis']]);
      const diag = diagRaw ? String(diagRaw).trim() : 'Unknown';
      if (diag && !['null', 'undefined', 'Unknown', ''].includes(diag)) {
        distributions.diagnosis[diag] = (distributions.diagnosis[diag] || 0) + 1;
      }
      
      const ageRaw = actualKeys['Age'] && row[actualKeys['Age']];
      if (ageRaw !== undefined && ageRaw !== null && !isNaN(Number(ageRaw))) {
        const bin = Math.floor(Number(ageRaw) / 5) * 5;
        const binLabel = `${bin}-${bin + 4}`;
        distributions.age[binLabel] = (distributions.age[binLabel] || 0) + 1;
      }

      const stayRaw = actualKeys['Stay'] && row[actualKeys['Stay']];
      if (stayRaw !== undefined && stayRaw !== null && !isNaN(Number(stayRaw))) {
        const stay = Number(stayRaw);
        let binLabel = '31+';
        if (stay <= 2) binLabel = '0-2';
        else if (stay <= 5) binLabel = '3-5';
        else if (stay <= 10) binLabel = '6-10';
        else if (stay <= 15) binLabel = '11-15';
        else if (stay <= 20) binLabel = '16-20';
        else if (stay <= 30) binLabel = '21-30';
        distributions.stay[binLabel] = (distributions.stay[binLabel] || 0) + 1;
      }
    });

    const formatCategorical = (obj: Record<string, number>) => 
      Object.entries(obj).map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value);

    const formatNumeric = (obj: Record<string, number>) =>
      Object.entries(obj)
        .map(([name, value]) => {
          const isPlus = name === '31+';
          const min = isPlus ? 31 : parseInt(name.split('-')[0]);
          const max = isPlus ? 999 : parseInt(name.split('-')[1]);
          return { name, value, min, max };
        })
        .sort((a, b) => a.min - b.min);

    return {
      sexData: formatCategorical(distributions.sex),
      resultData: formatCategorical(distributions.result),
      religionData: formatCategorical(distributions.religion),
      cityData: formatCategorical(distributions.city),
      diagnosisData: formatCategorical(distributions.diagnosis),
      nationalityData: formatCategorical(distributions.nationality),
      ageData: formatNumeric(distributions.age),
      stayData: formatNumeric(distributions.stay)
    };
  }, [data, actualKeys]);

  const handleRangeSelect = useCallback((displayName: 'Age' | 'Stay', entry: any) => {
    if (!entry) return;
    const actualKey = actualKeys[displayName];
    if (!actualKey) return;

    setFilterState(prev => ({
      ...prev,
      ranges: {
        ...prev.ranges,
        [actualKey]: {
          ...prev.ranges[actualKey],
          currentMin: entry.min,
          currentMax: entry.max
        }
      }
    }));
  }, [actualKeys, setFilterState]);

  const resetRange = useCallback((displayName: 'Age' | 'Stay') => {
    const actualKey = actualKeys[displayName];
    if (!actualKey) return;
    const range = filterState.ranges[actualKey];
    if (!range) return;

    setFilterState(prev => ({
      ...prev,
      ranges: {
        ...prev.ranges,
        [actualKey]: {
          ...prev.ranges[actualKey],
          currentMin: range.min,
          currentMax: range.max
        }
      }
    }));
  }, [actualKeys, filterState.ranges, setFilterState]);

  const handlePieClick = useCallback((displayName: string, entry: any) => {
    if (!entry || entry.name === 'Others') return;
    const actualKey = actualKeys[displayName];
    if (!actualKey) return;
    setFilterState(prev => {
      const current = prev.facets[actualKey] || [];
      const next = current.includes(entry.name) ? current.filter(v => v !== entry.name) : [...current, entry.name];
      return { ...prev, facets: { ...prev.facets, [actualKey]: next } };
    });
  }, [actualKeys, setFilterState]);

  const updateNumericRange = (displayName: 'Age' | 'Stay' | 'Admission Date', type: 'min' | 'max', value: string) => {
    const actualKey = actualKeys[displayName];
    if (!actualKey) return;
    
    let numericValue: number;
    if (displayName === 'Admission Date') {
      numericValue = new Date(value).getTime();
    } else {
      numericValue = parseInt(value);
    }
    
    if (isNaN(numericValue)) return;
    setFilterState(prev => ({
      ...prev,
      ranges: {
        ...prev.ranges,
        [actualKey]: {
          ...prev.ranges[actualKey],
          [type === 'min' ? 'currentMin' : 'currentMax']: numericValue
        }
      }
    }));
  };

  const renderPie = (chartData: any[], displayName: string, colorOffset: number = 0) => {
    if (chartData.length === 0) return <div className="h-full flex items-center justify-center text-slate-400 text-sm italic">No data</div>;
    const top10 = chartData.slice(0, 10);
    const othersValue = chartData.slice(10).reduce((acc, curr) => acc + curr.value, 0);
    const finalData = othersValue > 0 ? [...top10, { name: 'Others', value: othersValue }] : top10;
    return (
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={finalData} innerRadius={50} outerRadius={75} paddingAngle={3} dataKey="value" animationDuration={800} onClick={(entry) => handlePieClick(displayName, entry)} className="cursor-pointer outline-none">
            {finalData.map((entry, index) => (
              <Cell key={`cell-${displayName}-${index}`} fill={entry.name === 'Others' ? '#e2e8f0' : COLORS[(index + colorOffset) % COLORS.length]} className="hover:opacity-80 transition-opacity" />
            ))}
          </Pie>
          <Tooltip contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }} formatter={(v: number, n: string) => [v.toLocaleString(), n]} />
          <Legend payload={top10.map((e, i) => ({ id: e.name, type: 'circle', value: `${e.name} (${((e.value / data.length) * 100).toFixed(1)}%)`, color: COLORS[(i + colorOffset) % COLORS.length] }))} wrapperStyle={{ fontSize: '9px', paddingTop: '10px' }} layout="horizontal" verticalAlign="bottom" align="center" />
        </PieChart>
      </ResponsiveContainer>
    );
  };

  const generateInsights = async () => {
    if (data.length === 0 || !apiKey) return;
    setIsGenerating(true);
    localStorage.setItem('gemini_api_key', apiKey);
    try {
      const selectionPct = ((data.length / fullData.length) * 100).toFixed(1);
      const ai = new GoogleGenAI({ apiKey });
      const prompt = `Medical historian analysis of Mandatory Haifa clinical records.
      REPORT FIRST: ${data.length.toLocaleString()} records selected (${selectionPct}% of registry).
      Context: Top Diagnoses: ${stats.diagnosisData.slice(0, 3).map(d => d.name).join(', ')}.
      Hospital Stays: ${stats.stayData.map(s => `${s.name}: ${s.value}`).join(', ')}.
      Synthesize demographics (Age, Religion) vs clinical outcomes and hospitalization duration.`;
      
      const response = await ai.models.generateContent({ model: 'gemini-3-pro-preview', contents: prompt });
      setAiInsight(response.text || 'Synthesis unavailable.');
    } catch (error) {
      setAiInsight('Analysis service unavailable — check that the API key is valid and has Gemini access.');
    } finally {
      setIsGenerating(false);
    }
  };

  const selectionPercentage = ((data.length / fullData.length) * 100).toFixed(1);
  const getRangeValues = (key: 'Age' | 'Stay' | 'Admission Date') => {
    const r = filterState.ranges[actualKeys[key] || ''];
    return r ? { min: r.currentMin, max: r.currentMax, globalMin: r.min, globalMax: r.max } : { min: 0, max: 0, globalMin: 0, globalMax: 0 };
  };

  const isRangeModified = (key: 'Age' | 'Stay') => {
    const r = getRangeValues(key);
    return r.min !== r.globalMin || r.max !== r.globalMax;
  };

  return (
    <div className="flex w-full h-full overflow-hidden bg-slate-50">
      <FilterSidebar 
        data={fullData} 
        filterState={filterState} 
        setFilterState={setFilterState} 
        hideRangeKeys={['Admission Date [ISO]', 'Age', 'Days in Hospital (Calc)']}
      />
      
      <div className="flex-1 overflow-y-auto p-8 space-y-8 scroll-smooth custom-scrollbar">
        {/* Statistics Header */}
        <div className="bg-white p-6 rounded-3xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div className="flex items-center gap-6">
            <div className="w-12 h-12 bg-indigo-600 rounded-xl flex items-center justify-center text-white shadow-lg shadow-indigo-100"><Users size={24}/></div>
            <div>
              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Active Selection</p>
              <h2 className="text-2xl font-black text-slate-800">{data.length.toLocaleString()} <span className="text-sm font-bold text-indigo-500">/ {fullData.length.toLocaleString()}</span></h2>
            </div>
          </div>
          <div className="flex items-center gap-8">
            <div className="text-right">
              <div className="text-2xl font-black text-slate-800">{selectionPercentage}%</div>
              <p className="text-[9px] font-bold text-slate-400 uppercase tracking-widest">Registry Coverage</p>
            </div>
            <div className="w-32 h-2 bg-slate-100 rounded-full overflow-hidden"><div className="h-full bg-indigo-600 transition-all duration-700" style={{ width: `${selectionPercentage}%` }}></div></div>
          </div>
        </div>

        {/* Timeline (Full Breadth) */}
        <div className="bg-white p-8 rounded-3xl border border-slate-200 shadow-sm space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-slate-800 flex items-center gap-2"><TrendingUp size={20} className="text-indigo-600" /> Admission Timeline</h3>
            <div className="flex items-center gap-3 bg-slate-50 p-2 rounded-xl border border-slate-200">
              <Calendar size={14} className="text-slate-400" />
              <input type="date" value={new Date(getRangeValues('Admission Date').min).toISOString().split('T')[0]} onChange={(e) => updateNumericRange('Admission Date', 'min', e.target.value)} className="bg-transparent text-xs font-bold text-slate-700 outline-none" />
              <div className="h-4 w-px bg-slate-200"></div>
              <input type="date" value={new Date(getRangeValues('Admission Date').max).toISOString().split('T')[0]} onChange={(e) => updateNumericRange('Admission Date', 'max', e.target.value)} className="bg-transparent text-xs font-bold text-slate-700 outline-none" />
            </div>
          </div>
          <div className="h-[300px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={timelineStats} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <defs><linearGradient id="colorVal" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#4f46e5" stopOpacity={0.1}/><stop offset="95%" stopColor="#4f46e5" stopOpacity={0}/></linearGradient></defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis dataKey="name" fontSize={10} axisLine={false} tickLine={false} />
                <YAxis fontSize={10} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ borderRadius: '16px', border: 'none', boxShadow: '0 20px 25px -5px rgb(0 0 0 / 0.1)' }} />
                <Area type="monotone" dataKey="total" stroke="#cbd5e1" fill="transparent" strokeDasharray="5 5" name="Full Registry" />
                <Area type="monotone" dataKey="value" stroke="#4f46e5" strokeWidth={3} fill="url(#colorVal)" name="Selection" />
                <Brush dataKey="name" height={30} stroke="#4f46e5" fill="#f8fafc" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Charts Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {/* Categorical Pies */}
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm"><h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2"><HeartPulse size={18} className="text-rose-500" /> Diagnoses</h3><div className="h-[300px]">{renderPie(stats.diagnosisData, "Diagnosis", 0)}</div></div>
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm"><h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2"><CheckCircle2 size={18} className="text-emerald-500" /> Clinical Result</h3><div className="h-[300px]">{renderPie(stats.resultData, "Result", 2)}</div></div>
          
          {/* Age Distribution (Interactive) */}
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex flex-col group/card">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold text-slate-800 flex items-center gap-2"><Baby size={18} className="text-indigo-600" /> Age Profile</h3>
              <div className="flex items-center gap-2">
                {isRangeModified('Age') && (
                  <button onClick={() => resetRange('Age')} className="text-slate-300 hover:text-indigo-600 transition-colors p-1" title="Reset filter"><RotateCcw size={12}/></button>
                )}
                <div className="flex items-center gap-1 bg-slate-50 px-2 py-1 rounded-lg border border-slate-100">
                  <input type="number" value={getRangeValues('Age').min} onChange={(e) => updateNumericRange('Age', 'min', e.target.value)} className="w-8 bg-transparent text-[10px] font-bold text-indigo-600 outline-none text-center" />
                  <span className="text-[10px] text-slate-300">-</span>
                  <input type="number" value={getRangeValues('Age').max} onChange={(e) => updateNumericRange('Age', 'max', e.target.value)} className="w-8 bg-transparent text-[10px] font-bold text-indigo-600 outline-none text-center" />
                </div>
              </div>
            </div>
            <div className="flex-1 min-h-[250px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={stats.ageData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis dataKey="name" fontSize={9} axisLine={false} tickLine={false} />
                  <YAxis fontSize={9} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }} />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]} className="cursor-pointer">
                    {stats.ageData.map((entry, index) => {
                      const ageRange = getRangeValues('Age');
                      const isActive = entry.min >= ageRange.min && entry.max <= ageRange.max;
                      return (
                        <Cell 
                          key={`cell-age-${index}`} 
                          fill={isActive ? '#4f46e5' : '#e2e8f0'} 
                          className="transition-all duration-300 hover:opacity-80"
                          onClick={() => handleRangeSelect('Age', entry)}
                        />
                      );
                    })}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p className="text-[9px] text-slate-400 text-center mt-2 font-medium italic">Click bars to select a specific 5-year cohort</p>
          </div>

          {/* Stay Duration (Interactive) */}
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex flex-col group/card">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold text-slate-800 flex items-center gap-2"><Timer size={18} className="text-cyan-500" /> Hospital Stay</h3>
              <div className="flex items-center gap-2">
                {isRangeModified('Stay') && (
                  <button onClick={() => resetRange('Stay')} className="text-slate-300 hover:text-cyan-600 transition-colors p-1" title="Reset filter"><RotateCcw size={12}/></button>
                )}
                <div className="flex items-center gap-1 bg-slate-50 px-2 py-1 rounded-lg border border-slate-100">
                  <input type="number" value={getRangeValues('Stay').min} onChange={(e) => updateNumericRange('Stay', 'min', e.target.value)} className="w-8 bg-transparent text-[10px] font-bold text-cyan-600 outline-none text-center" />
                  <span className="text-[10px] text-slate-300">-</span>
                  <input type="number" value={getRangeValues('Stay').max} onChange={(e) => updateNumericRange('Stay', 'max', e.target.value)} className="w-8 bg-transparent text-[10px] font-bold text-cyan-600 outline-none text-center" />
                </div>
              </div>
            </div>
            <div className="flex-1 min-h-[250px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={stats.stayData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis dataKey="name" fontSize={9} axisLine={false} tickLine={false} />
                  <YAxis fontSize={9} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }} />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]} className="cursor-pointer">
                    {stats.stayData.map((entry, index) => {
                      const stayRange = getRangeValues('Stay');
                      const isActive = entry.min >= stayRange.min && entry.max <= stayRange.max;
                      return (
                        <Cell 
                          key={`cell-stay-${index}`} 
                          fill={isActive ? '#06b6d4' : '#e2e8f0'} 
                          className="transition-all duration-300 hover:opacity-80"
                          onClick={() => handleRangeSelect('Stay', entry)}
                        />
                      );
                    })}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p className="text-[9px] text-slate-400 text-center mt-2 font-medium italic">Click bars to isolate specific stay durations</p>
          </div>

          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm"><h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2"><Sparkles size={18} className="text-amber-500" /> Religion</h3><div className="h-[300px]">{renderPie(stats.religionData, "Religion", 4)}</div></div>
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm"><h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2"><Globe size={18} className="text-emerald-500" /> Nationality</h3><div className="h-[300px]">{renderPie(stats.nationalityData, "Nationality", 6)}</div></div>
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm"><h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2"><Users size={18} className="text-indigo-500" /> Sex Distribution</h3><div className="h-[300px]">{renderPie(stats.sexData, "Sex", 8)}</div></div>
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm"><h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2"><MapPin size={18} className="text-slate-500" /> Origin Cities</h3><div className="h-[300px]">{renderPie(stats.cityData, "City", 1)}</div></div>
        </div>

        {/* AI Analysis Section */}
        <div className="bg-indigo-900 text-indigo-100 p-8 rounded-3xl shadow-2xl relative overflow-hidden group">
          <div className="absolute top-0 right-0 -m-8 w-64 h-64 bg-indigo-500/10 rounded-full blur-3xl"></div>
          <div className="relative z-10 flex flex-col md:flex-row items-start gap-8">
            <div className="shrink-0 flex flex-col items-center">
              <div className="w-16 h-16 bg-white/10 rounded-2xl flex items-center justify-center text-indigo-300 mb-4 backdrop-blur-sm border border-white/10"><BrainCircuit size={32} /></div>
              <button onClick={generateInsights} disabled={isGenerating || data.length === 0 || !apiKey} className="px-6 py-3 bg-white text-indigo-900 rounded-xl font-bold text-sm hover:bg-indigo-50 transition-all active:scale-[0.98] shadow-xl disabled:opacity-50 whitespace-nowrap">{isGenerating ? 'Synthesizing...' : 'Generate AI Synthesis'}</button>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="Gemini API key"
                className="mt-3 w-full max-w-[180px] px-3 py-2 bg-white/10 border border-white/20 rounded-lg text-xs text-indigo-100 placeholder:text-indigo-300/60 outline-none focus:border-white/40"
              />
              <a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer" className="mt-2 text-[10px] text-indigo-300/70 hover:text-indigo-200 underline">get a key</a>
            </div>
            <div className="flex-1">
              <h3 className="text-xl font-bold mb-4">Smart Historical Synthesis</h3>
              <div className="prose prose-invert prose-sm max-w-none">
                {aiInsight
                  ? <div className="text-indigo-100 leading-relaxed text-sm whitespace-pre-wrap">{aiInsight}</div>
                  : <p className="text-indigo-200/70 text-sm italic">
                      Analyze historical clinical patterns over the current selection. Use the charts to filter interactively by age, stay duration, or categorical attributes.
                      {!apiKey && ' Paste your own Gemini API key to enable this — it is stored in your browser and never sent anywhere but Google.'}
                    </p>}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default StatisticsView;
