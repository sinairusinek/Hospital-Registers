
import React, { useMemo, useState, useEffect, useCallback } from 'react';
import { 
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, 
  PieChart, Pie, Cell, AreaChart, Area, Legend
} from 'recharts';
import { GoogleGenAI } from "@google/genai";
import { TrendingUp, Users, MapPin, HeartPulse, Globe, CheckCircle2, Sparkles, BrainCircuit } from 'lucide-react';
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

  // Enhanced robust key mapping for historical hospital registry
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

  const stats = useMemo(() => {
    const sexDist: Record<string, number> = {};
    const resultDist: Record<string, number> = {};
    const diagnosisDist: Record<string, number> = {};
    const admissionTimeline: Record<string, number> = {};
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

      const date = String((actualKeys['Admission Date'] && row[actualKeys['Admission Date']]) || '');
      if (date && date.includes('-')) {
        const parts = date.split('-');
        if (parts.length >= 2) {
          const key = `${parts[0]}-${parts[1]}`;
          admissionTimeline[key] = (admissionTimeline[key] || 0) + 1;
        }
      }
    });

    const formatForChart = (obj: Record<string, number>) => 
      Object.entries(obj)
        .map(([name, value]) => ({ name, value }))
        .sort((a, b) => b.value - a.value);

    return {
      sexData: formatForChart(sexDist),
      resultData: formatForChart(resultDist),
      religionData: formatForChart(religionDist),
      cityData: formatForChart(cityDist),
      diagnosisData: formatForChart(diagnosisDist),
      nationalityData: formatForChart(nationalityDist),
      timelineData: Object.entries(admissionTimeline)
        .map(([name, value]) => ({ name, value }))
        .sort((a, b) => a.name.localeCompare(b.name))
    };
  }, [data, actualKeys]);

  const handlePieClick = useCallback((displayName: string, entry: any) => {
    if (!entry || entry.name === 'Others') return;
    const actualKey = actualKeys[displayName];
    if (!actualKey) return;
    
    setFilterState(prev => {
      const current = prev.facets[actualKey] || [];
      const next = current.includes(entry.name) 
        ? current.filter(v => v !== entry.name) 
        : [...current, entry.name];
      return { ...prev, facets: { ...prev.facets, [actualKey]: next } };
    });
  }, [actualKeys, setFilterState]);

  const renderPie = (chartData: any[], displayName: string, colorOffset: number = 0) => {
    if (chartData.length === 0) return <div className="h-full flex items-center justify-center text-slate-400 text-sm">No data available</div>;
    
    // Data is already sorted by frequency in the stats memo
    const top10 = chartData.slice(0, 10);
    const othersValue = chartData.slice(10).reduce((acc, curr) => acc + curr.value, 0);
    
    const finalData = othersValue > 0 
      ? [...top10, { name: 'Others', value: othersValue }]
      : top10;

    return (
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie 
            data={finalData} 
            innerRadius={50} 
            outerRadius={75} 
            paddingAngle={3} 
            dataKey="value"
            animationDuration={800}
            onClick={(entry) => handlePieClick(displayName, entry)}
            className="cursor-pointer outline-none"
          >
            {finalData.map((entry, index) => (
              <Cell 
                key={`cell-${displayName}-${index}`} 
                fill={entry.name === 'Others' ? '#e2e8f0' : COLORS[(index + colorOffset) % COLORS.length]} 
                className="hover:opacity-80 transition-opacity"
              />
            ))}
          </Pie>
          <Tooltip 
            contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }} 
            // Formatter shows [Value, Name] which maps to "Name: Value" in standard Recharts UI
            formatter={(value: number, name: string) => [value.toLocaleString(), name]}
          />
          <Legend 
            payload={top10.map((entry, index) => ({
              id: entry.name,
              type: 'circle',
              value: `${entry.name} (${((entry.value / data.length) * 100).toFixed(1)}%)`,
              color: COLORS[(index + colorOffset) % COLORS.length]
            }))}
            wrapperStyle={{ fontSize: '9px', paddingTop: '10px' }} 
            layout="horizontal" 
            verticalAlign="bottom" 
            align="center" 
          />
        </PieChart>
      </ResponsiveContainer>
    );
  };

  const generateInsights = async () => {
    if (data.length === 0) return;
    setIsGenerating(true);
    try {
      const ai = new GoogleGenAI({ apiKey: process.env.API_KEY as string });
      const prompt = `
        You are an expert medical historian analyzing historical clinical records from Haifa Government Hospital (Mandatory Palestine).
        The hospital was primarily dedicated to infectious diseases in a multi-cultural port city.

        Current Data Context:
        - Total Sample: ${data.length} records.
        - Top Diagnoses: ${stats.diagnosisData.slice(0, 5).map(d => `${d.name} (${d.value})`).join(', ')}
        - Geographical Context: ${stats.cityData.slice(0, 5).map(d => `${d.name} (${d.value})`).join(', ')}
        - Outcomes: ${stats.resultData.map(d => `${d.name}: ${d.value}`).join(', ')}

        Task: Provide a concise synthesis of these clinical patterns. Focus on the interplay between Haifa's diverse population and the recorded medical outcomes.
      `;

      const response = await ai.models.generateContent({
        model: 'gemini-3-pro-preview',
        contents: prompt,
      });

      setAiInsight(response.text || 'Unable to generate insights.');
    } catch (error) {
      console.error('AI error:', error);
      setAiInsight('Insight engine disconnected.');
    } finally {
      setIsGenerating(false);
    }
  };

  useEffect(() => {
    setAiInsight('');
  }, [data]);

  const selectionPercentage = ((data.length / fullData.length) * 100).toFixed(1);

  return (
    <div className="flex w-full h-full overflow-hidden bg-slate-50">
      <FilterSidebar 
        data={fullData} 
        filterState={filterState} 
        setFilterState={setFilterState} 
      />
      
      <div className="flex-1 overflow-y-auto p-8 space-y-8 scroll-smooth custom-scrollbar">
        {/* Active Selection Header Card - Includes count and percentage */}
        <div className="bg-white p-8 rounded-3xl border border-slate-200 shadow-sm flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-6">
            <div className="w-16 h-16 bg-indigo-600 rounded-2xl flex items-center justify-center text-white shadow-lg shadow-indigo-100 shrink-0">
              <Users size={32}/>
            </div>
            <div>
              <p className="text-xs font-bold text-slate-400 uppercase tracking-[0.2em] mb-1">Active Selection</p>
              <h2 className="text-4xl font-black text-slate-800 leading-none">
                {data.length.toLocaleString()} 
                <span className="text-lg font-bold text-indigo-500 ml-3">/ {fullData.length.toLocaleString()}</span>
              </h2>
            </div>
          </div>
          
          <div className="flex flex-col items-center md:items-end">
            <div className="text-3xl font-black text-slate-800">{selectionPercentage}%</div>
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">of total registry</p>
            <div className="w-48 h-2 bg-slate-100 rounded-full mt-3 overflow-hidden relative">
              <div 
                className="absolute left-0 top-0 h-full bg-indigo-600 transition-all duration-700 ease-out" 
                style={{ width: `${selectionPercentage}%` }}
              ></div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
          <div className="lg:col-span-2 space-y-8">
            {/* Timeline */}
            <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
              <div className="flex items-center justify-between mb-6">
                <h3 className="font-bold text-slate-800 flex items-center gap-2">
                  <TrendingUp size={18} className="text-indigo-600" />
                  Admission Timeline (Full Historical Span)
                </h3>
                <span className="text-[10px] bg-slate-100 px-2 py-1 rounded-full text-slate-500 font-bold uppercase">{stats.timelineData.length} active months</span>
              </div>
              <div className="h-[300px]">
                {stats.timelineData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={stats.timelineData}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                      <XAxis dataKey="name" fontSize={9} axisLine={false} tickLine={false} tickMargin={10} />
                      <YAxis fontSize={10} axisLine={false} tickLine={false} />
                      <Tooltip contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }} />
                      <Area type="monotone" dataKey="value" stroke="#4f46e5" strokeWidth={3} fill="#4f46e5" fillOpacity={0.1} />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex items-center justify-center text-slate-400 text-sm italic">No timeline data available</div>
                )}
              </div>
            </div>

            {/* Interactive Distribution Charts */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm transition-shadow hover:shadow-md">
                <h3 className="font-bold text-slate-800 mb-6 flex items-center gap-2">
                  <HeartPulse size={18} className="text-rose-500" />
                  Primary Diagnoses
                </h3>
                <div className="h-[320px]">{renderPie(stats.diagnosisData, "Diagnosis", 0)}</div>
              </div>
              
              <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm transition-shadow hover:shadow-md">
                <h3 className="font-bold text-slate-800 mb-6 flex items-center gap-2">
                  <CheckCircle2 size={18} className="text-emerald-500" />
                  Clinical Results
                </h3>
                <div className="h-[320px]">{renderPie(stats.resultData, "Result", 2)}</div>
              </div>

              <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm transition-shadow hover:shadow-md">
                <h3 className="font-bold text-slate-800 mb-6 flex items-center gap-2">
                  <Sparkles size={18} className="text-amber-500" />
                  Religious Groups
                </h3>
                <div className="h-[320px]">{renderPie(stats.religionData, "Religion", 4)}</div>
              </div>

              <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm transition-shadow hover:shadow-md">
                <h3 className="font-bold text-slate-800 mb-6 flex items-center gap-2">
                  <Globe size={18} className="text-cyan-500" />
                  Nationalities
                </h3>
                <div className="h-[320px]">{renderPie(stats.nationalityData, "Nationality", 6)}</div>
              </div>

              <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm transition-shadow hover:shadow-md">
                <h3 className="font-bold text-slate-800 mb-6 flex items-center gap-2">
                  <Users size={18} className="text-indigo-500" />
                  Sex Distribution
                </h3>
                <div className="h-[320px]">{renderPie(stats.sexData, "Sex", 8)}</div>
              </div>

              <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm transition-shadow hover:shadow-md">
                <h3 className="font-bold text-slate-800 mb-6 flex items-center gap-2">
                  <MapPin size={18} className="text-slate-500" />
                  Origin Cities
                </h3>
                <div className="h-[320px]">{renderPie(stats.cityData, "City", 1)}</div>
              </div>
            </div>
          </div>

          {/* AI Insights Sidebar */}
          <div className="lg:sticky lg:top-8">
            <div className="bg-indigo-900 text-indigo-100 p-8 rounded-3xl shadow-2xl relative overflow-hidden group min-h-[500px] flex flex-col">
              <div className="absolute top-0 right-0 -m-8 w-48 h-48 bg-indigo-500/10 rounded-full blur-3xl group-hover:bg-indigo-500/20 transition-colors"></div>
              <div className="relative z-10 h-full flex flex-col flex-1">
                <div className="flex items-center gap-2 mb-6">
                  <BrainCircuit size={24} className="text-indigo-300" />
                  <h3 className="text-xl font-bold">Smart Analysis</h3>
                </div>
                
                <div className="flex-1 overflow-y-auto pr-2 custom-scrollbar mb-6">
                  {isGenerating ? (
                    <div className="space-y-4 animate-pulse">
                      <div className="h-4 bg-indigo-800/50 rounded w-3/4"></div>
                      <div className="h-4 bg-indigo-800/50 rounded"></div>
                      <div className="h-4 bg-indigo-800/50 rounded w-5/6"></div>
                    </div>
                  ) : (
                    <div className="prose prose-invert prose-sm">
                      {aiInsight ? (
                        <div className="text-indigo-100 leading-relaxed text-sm whitespace-pre-wrap">{aiInsight}</div>
                      ) : (
                        <div className="text-indigo-200/70 text-sm italic space-y-4">
                          <p>Analyze clinical patterns for the currently filtered selection of {data.length.toLocaleString()} records.</p>
                          <div className="mt-6 p-4 bg-white/5 rounded-2xl border border-white/10">
                            <p className="text-[10px] uppercase font-bold tracking-widest text-indigo-400 mb-2">Interactive Dashboard:</p>
                            <p className="text-xs">Click on any pie chart slice to apply a cross-filter across all visualizations. Legends show the top 10 most frequent categories.</p>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                <button 
                  onClick={generateInsights} 
                  disabled={isGenerating || data.length === 0}
                  className="w-full py-4 bg-white text-indigo-900 rounded-xl font-bold text-sm hover:bg-indigo-50 transition-all active:scale-[0.98] disabled:opacity-50 shadow-xl mt-auto"
                >
                  {isGenerating ? 'Synthesizing...' : 'Generate AI Synthesis'}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default StatisticsView;
