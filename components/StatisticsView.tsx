
import React, { useMemo, useState, useEffect, useCallback } from 'react';
import { 
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, 
  PieChart, Pie, Cell, AreaChart, Area, Legend, Brush
} from 'recharts';
import { GoogleGenAI } from "@google/genai";
import { TrendingUp, Users, MapPin, HeartPulse, Globe, CheckCircle2, Sparkles, BrainCircuit, Calendar } from 'lucide-react';
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

  // Robust key mapping
  const actualKeys = useMemo(() => {
    if (fullData.length === 0) return {};
    const dataKeys = Object.keys(fullData[0]);
    const targets = [
      { id: 'Sex', aliases: ['sex', 'gender'] },
      { id: 'Result', aliases: ['standardized result', 'result', 'outcome', 'standardized_result'] },
      { id: 'Religion', aliases: ['standardized religion', 'religion', 'standardized_religion'] },
      { id: 'Diagnosis', aliases: ['standardprimaryicd9names', 'standardprimaryicd9name', 'diagnosis', 'standardized diagnosis', 'primary-icd9', 'primary diagnosis'] },
      { id: 'Admission Date', aliases: ['admission date [iso]', 'admission date', 'date'] },
      { id: 'City', aliases: ['city', 'town', 'residence'] },
      { id: 'Nationality', aliases: ['standardnationality', 'nationality', 'standard_nationality'] }
    ];
    const mapping: Record<string, string> = {};
    targets.forEach(target => {
      const found = dataKeys.find(k => {
        const lowerK = k.toLowerCase().trim();
        return target.id.toLowerCase() === lowerK || target.aliases.includes(lowerK);
      });
      if (found) mapping[target.id] = found;
    });
    return mapping;
  }, [fullData]);

  // Comprehensive stats for the entire span (not just filtered) to provide full timeline context
  const timelineStats = useMemo(() => {
    const admissionTimeline: Record<string, number> = {};
    const dateKey = actualKeys['Admission Date'];
    if (!dateKey) return [];

    // Use fullData to get the total possible span
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
        // Find filtered value for the same month
        const filteredCount = data.filter(row => {
          const d = String(row[dateKey] || '');
          return d.startsWith(name);
        }).length;
        
        return { name, total: value, value: filteredCount };
      })
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [fullData, data, actualKeys]);

  const stats = useMemo(() => {
    const sexDist: Record<string, number> = {};
    const resultDist: Record<string, number> = {};
    const diagnosisDist: Record<string, number> = {};
    const religionDist: Record<string, number> = {};
    const cityDist: Record<string, number> = {};
    const nationalityDist: Record<string, number> = {};

    data.forEach(row => {
      const sex = String((actualKeys['Sex'] && row[actualKeys['Sex']]) || 'Not Specified');
      sexDist[sex] = (sexDist[sex] || 0) + 1;
      const res = String((actualKeys['Result'] && row[actualKeys['Result']]) || 'Unknown');
      resultDist[res] = (resultDist[res] || 0) + 1;
      const rel = String((actualKeys['Religion'] && row[actualKeys['Religion']]) || 'Unknown');
      religionDist[rel] = (religionDist[rel] || 0) + 1;
      const city = String((actualKeys['City'] && row[actualKeys['City']]) || 'Unknown');
      cityDist[city] = (cityDist[city] || 0) + 1;
      const nat = String((actualKeys['Nationality'] && row[actualKeys['Nationality']]) || 'Unknown');
      nationalityDist[nat] = (nationalityDist[nat] || 0) + 1;
      const diagRaw = (actualKeys['Diagnosis'] && row[actualKeys['Diagnosis']]);
      const diag = diagRaw ? String(diagRaw).trim() : 'Unknown';
      if (diag && diag !== 'null' && diag !== 'undefined' && diag !== 'Unknown' && diag !== '') {
        diagnosisDist[diag] = (diagnosisDist[diag] || 0) + 1;
      }
    });

    const formatForChart = (obj: Record<string, number>) => 
      Object.entries(obj).map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value);

    return {
      sexData: formatForChart(sexDist),
      resultData: formatForChart(resultDist),
      religionData: formatForChart(religionDist),
      cityData: formatForChart(cityDist),
      diagnosisData: formatForChart(diagnosisDist),
      nationalityData: formatForChart(nationalityDist)
    };
  }, [data, actualKeys]);

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

  const updateDateRange = (type: 'min' | 'max', value: string) => {
    const actualKey = actualKeys['Admission Date'];
    if (!actualKey) return;
    const timestamp = new Date(value).getTime();
    if (isNaN(timestamp)) return;
    setFilterState(prev => ({
      ...prev,
      ranges: {
        ...prev.ranges,
        [actualKey]: {
          ...prev.ranges[actualKey],
          [type === 'min' ? 'currentMin' : 'currentMax']: timestamp
        }
      }
    }));
  };

  const renderPie = (chartData: any[], displayName: string, colorOffset: number = 0) => {
    if (chartData.length === 0) return <div className="h-full flex items-center justify-center text-slate-400 text-sm">No data available</div>;
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
          <Tooltip contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }} formatter={(value: number, name: string) => [value.toLocaleString(), name]} />
          <Legend payload={top10.map((entry, index) => ({ id: entry.name, type: 'circle', value: `${entry.name} (${((entry.value / data.length) * 100).toFixed(1)}%)`, color: COLORS[(index + colorOffset) % COLORS.length] }))} wrapperStyle={{ fontSize: '9px', paddingTop: '10px' }} layout="horizontal" verticalAlign="bottom" align="center" />
        </PieChart>
      </ResponsiveContainer>
    );
  };

  const generateInsights = async () => {
    if (data.length === 0) return;
    setIsGenerating(true);
    try {
      const ai = new GoogleGenAI({ apiKey: process.env.API_KEY as string });
      const prompt = `Medical historian analysis of ${data.length} records. Top diagnoses: ${stats.diagnosisData.slice(0, 3).map(d => d.name).join(', ')}. Context: Haifa Mandatory Palestine.`;
      const response = await ai.models.generateContent({ model: 'gemini-3-pro-preview', contents: prompt });
      setAiInsight(response.text || 'Unable to generate insights.');
    } catch (error) {
      setAiInsight('Insight engine disconnected.');
    } finally {
      setIsGenerating(false);
    }
  };

  const selectionPercentage = ((data.length / fullData.length) * 100).toFixed(1);
  const dateKey = actualKeys['Admission Date'] || '';
  const currentRange = filterState.ranges[dateKey];
  const minDateStr = currentRange ? new Date(currentRange.currentMin).toISOString().split('T')[0] : '';
  const maxDateStr = currentRange ? new Date(currentRange.currentMax).toISOString().split('T')[0] : '';

  return (
    <div className="flex w-full h-full overflow-hidden bg-slate-50">
      <FilterSidebar 
        data={fullData} 
        filterState={filterState} 
        setFilterState={setFilterState} 
        hideRangeKeys={['Admission Date [ISO]']}
      />
      
      <div className="flex-1 overflow-y-auto p-8 space-y-8 scroll-smooth custom-scrollbar">
        {/* Header Stats */}
        <div className="bg-white p-6 rounded-3xl border border-slate-200 shadow-sm flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-6">
            <div className="w-12 h-12 bg-indigo-600 rounded-xl flex items-center justify-center text-white shadow-lg shadow-indigo-100 shrink-0">
              <Users size={24}/>
            </div>
            <div>
              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Active Selection</p>
              <h2 className="text-2xl font-black text-slate-800 leading-none">
                {data.length.toLocaleString()} 
                <span className="text-sm font-bold text-indigo-500 ml-2">/ {fullData.length.toLocaleString()}</span>
              </h2>
            </div>
          </div>
          <div className="flex items-center gap-8">
            <div className="text-right">
              <div className="text-2xl font-black text-slate-800">{selectionPercentage}%</div>
              <p className="text-[9px] font-bold text-slate-400 uppercase tracking-widest">Global Coverage</p>
            </div>
            <div className="w-32 h-2 bg-slate-100 rounded-full overflow-hidden relative">
              <div className="absolute left-0 top-0 h-full bg-indigo-600 transition-all duration-700" style={{ width: `${selectionPercentage}%` }}></div>
            </div>
          </div>
        </div>

        {/* Full Breadth Timeline Section */}
        <div className="bg-white p-8 rounded-3xl border border-slate-200 shadow-sm space-y-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <h3 className="font-bold text-slate-800 flex items-center gap-2">
              <TrendingUp size={20} className="text-indigo-600" />
              Admission Timeline & Span Controls
            </h3>
            
            <div className="flex items-center gap-3 bg-slate-50 p-2 rounded-xl border border-slate-200">
              <div className="flex items-center gap-2">
                <Calendar size={14} className="text-slate-400" />
                <input type="date" value={minDateStr} onChange={(e) => updateDateRange('min', e.target.value)} className="bg-transparent text-xs font-bold text-slate-700 outline-none" />
              </div>
              <div className="h-4 w-px bg-slate-200"></div>
              <div className="flex items-center gap-2">
                <input type="date" value={maxDateStr} onChange={(e) => updateDateRange('max', e.target.value)} className="bg-transparent text-xs font-bold text-slate-700 outline-none" />
              </div>
            </div>
          </div>

          <div className="h-[350px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={timelineStats} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#4f46e5" stopOpacity={0.1}/>
                    <stop offset="95%" stopColor="#4f46e5" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis dataKey="name" fontSize={10} axisLine={false} tickLine={false} tickMargin={10} />
                <YAxis fontSize={10} axisLine={false} tickLine={false} />
                <Tooltip 
                  contentStyle={{ borderRadius: '16px', border: 'none', boxShadow: '0 20px 25px -5px rgb(0 0 0 / 0.1)' }} 
                  labelClassName="font-bold text-indigo-600 mb-1"
                />
                <Area type="monotone" dataKey="total" stroke="#cbd5e1" fill="transparent" strokeDasharray="5 5" name="Registry Total" />
                <Area type="monotone" dataKey="value" stroke="#4f46e5" strokeWidth={3} fillOpacity={1} fill="url(#colorValue)" name="Current Selection" />
                <Brush dataKey="name" height={30} stroke="#4f46e5" fill="#f8fafc" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Pies Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm"><h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2"><HeartPulse size={18} className="text-rose-500" /> Diagnoses</h3><div className="h-[300px]">{renderPie(stats.diagnosisData, "Diagnosis", 0)}</div></div>
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm"><h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2"><CheckCircle2 size={18} className="text-emerald-500" /> Results</h3><div className="h-[300px]">{renderPie(stats.resultData, "Result", 2)}</div></div>
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm"><h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2"><Sparkles size={18} className="text-amber-500" /> Religion</h3><div className="h-[300px]">{renderPie(stats.religionData, "Religion", 4)}</div></div>
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm"><h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2"><Globe size={18} className="text-cyan-500" /> Nationality</h3><div className="h-[300px]">{renderPie(stats.nationalityData, "Nationality", 6)}</div></div>
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm"><h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2"><Users size={18} className="text-indigo-500" /> Sex</h3><div className="h-[300px]">{renderPie(stats.sexData, "Sex", 8)}</div></div>
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm"><h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2"><MapPin size={18} className="text-slate-500" /> Cities</h3><div className="h-[300px]">{renderPie(stats.cityData, "City", 1)}</div></div>
        </div>

        {/* Smart Analysis Section - Relocated Down */}
        <div className="bg-indigo-900 text-indigo-100 p-8 rounded-3xl shadow-2xl relative overflow-hidden group">
          <div className="absolute top-0 right-0 -m-8 w-64 h-64 bg-indigo-500/10 rounded-full blur-3xl"></div>
          <div className="relative z-10 flex flex-col md:flex-row items-start gap-8">
            <div className="shrink-0 flex flex-col items-center">
              <div className="w-16 h-16 bg-white/10 rounded-2xl flex items-center justify-center text-indigo-300 mb-4 backdrop-blur-sm border border-white/10">
                <BrainCircuit size={32} />
              </div>
              <button 
                onClick={generateInsights} 
                disabled={isGenerating || data.length === 0}
                className="px-6 py-3 bg-white text-indigo-900 rounded-xl font-bold text-sm hover:bg-indigo-50 transition-all active:scale-[0.98] shadow-xl disabled:opacity-50 whitespace-nowrap"
              >
                {isGenerating ? 'Synthesizing...' : 'Generate AI Insight'}
              </button>
            </div>
            <div className="flex-1">
              <h3 className="text-xl font-bold mb-4">Smart Historical Synthesis</h3>
              <div className="prose prose-invert prose-sm max-w-none">
                {aiInsight ? (
                  <div className="text-indigo-100 leading-relaxed text-sm whitespace-pre-wrap">{aiInsight}</div>
                ) : (
                  <p className="text-indigo-200/70 text-sm italic">Select a clinical cohort and click generate to synthesize historical patterns. The dashboard is interactive: click pie slices or adjust the timeline above to narrow your clinical focus.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default StatisticsView;
