
import React, { useMemo, useState, useEffect } from 'react';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, 
  PieChart, Pie, Cell, LineChart, Line, AreaChart, Area, Legend
} from 'recharts';
import { GoogleGenAI } from "@google/genai";
import { TrendingUp, Users, Activity, Clock, Sparkles, BrainCircuit, Info, MapPin } from 'lucide-react';
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
      { id: 'Standardized Result', aliases: ['standardized result', 'result', 'outcome', 'standardized_result'] },
      { id: 'Standardized Religion', aliases: ['standardized religion', 'religion', 'standardized_religion'] },
      { id: 'standardprimaryICD9names', aliases: ['standardprimaryicd9names', 'standardprimaryicd9name', 'diagnosis', 'standardized diagnosis', 'primary-icd9', 'primary diagnosis'] },
      { id: 'Admission Date [ISO]', aliases: ['admission date [iso]', 'admission date', 'date'] },
      { id: 'City', aliases: ['city', 'town', 'residence'] }
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

    data.forEach(row => {
      // Sex
      const sexKey = actualKeys['Sex'];
      const sex = String((sexKey && row[sexKey]) || 'Not Specified');
      sexDist[sex] = (sexDist[sex] || 0) + 1;

      // Results
      const resKey = actualKeys['Standardized Result'];
      const res = String((resKey && row[resKey]) || 'Unknown');
      resultDist[res] = (resultDist[res] || 0) + 1;

      // Standardized Religion
      const relKey = actualKeys['Standardized Religion'];
      const rel = String((relKey && row[relKey]) || 'Unknown');
      religionDist[rel] = (religionDist[rel] || 0) + 1;

      // Cities
      const cityKey = actualKeys['City'];
      const city = String((cityKey && row[cityKey]) || 'Unknown');
      cityDist[city] = (cityDist[city] || 0) + 1;

      // Diagnoses - Using robust mapping
      const diagKey = actualKeys['standardprimaryICD9names'];
      const diagRaw = (diagKey && row[diagKey]);
      const diag = diagRaw ? String(diagRaw).trim() : 'Unknown';
      
      if (diag && diag !== 'null' && diag !== 'undefined' && diag !== 'Unknown' && diag !== '') {
        diagnosisDist[diag] = (diagnosisDist[diag] || 0) + 1;
      }

      // Timeline
      const dateKey = actualKeys['Admission Date [ISO]'];
      const date = String((dateKey && row[dateKey]) || '');
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
      cityData: formatForChart(cityDist).slice(0, 10),
      diagnosisData: formatForChart(diagnosisDist).slice(0, 10),
      timelineData: Object.entries(admissionTimeline)
        .map(([name, value]) => ({ name, value }))
        .sort((a, b) => a.name.localeCompare(b.name))
        .slice(-36)
    };
  }, [data, actualKeys]);

  const generateInsights = async () => {
    if (data.length === 0) return;
    setIsGenerating(true);
    try {
      const ai = new GoogleGenAI({ apiKey: process.env.API_KEY || '' });
      const prompt = `
        You are an expert medical historian analyzing historical clinical records from Haifa Government Hospital (Mandatory Palestine).
        The hospital was primarily dedicated to infectious diseases in a multi-cultural port city.

        Current Data Context:
        - Total Sample: ${data.length} records.
        - Primary Clinical Burden (Diagnoses): ${stats.diagnosisData.map(d => `${d.name} (${d.value})`).join(', ')}
        - Geographical Context (Top Cities): ${stats.cityData.map(d => `${d.name} (${d.value})`).join(', ')}
        - Outcomes: ${stats.resultData.map(d => `${d.name}: ${d.value}`).join(', ')}

        Task: Provide a synthesis of these clinical patterns. Discuss how the infectious disease focus of this Haifa hospital relates to the observed diagnoses and the demographic diversity of the region during the Mandatory period.
      `;

      const response = await ai.models.generateContent({
        model: 'gemini-3-flash-preview',
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

  const StatCard = ({ title, value, icon, color, tooltip }: { title: string, value: string, icon: React.ReactNode, color: string, tooltip: string }) => (
    <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex items-center gap-4 group relative">
      <div className={`w-12 h-12 rounded-xl flex items-center justify-center text-white shrink-0 shadow-sm ${color}`}>
        {icon}
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest flex items-center gap-1.5 mb-1">
          {title}
          <span className="cursor-help text-slate-300 hover:text-indigo-500 transition-colors">
            <Info size={12} />
          </span>
        </p>
        <p className="text-xl font-black text-slate-800 leading-tight truncate" title={value}>{value}</p>
      </div>
      
      {/* Tooltip relocated to pop DOWN (top-full + mt-3) to avoid being hidden by the app header */}
      <div className="absolute top-full left-1/2 -translate-x-1/2 mt-3 w-64 p-3 bg-slate-800 text-white text-[11px] leading-relaxed rounded-xl shadow-2xl opacity-0 group-hover:opacity-100 pointer-events-none transition-all duration-200 z-[100] text-center scale-95 group-hover:scale-100">
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 border-8 border-transparent border-b-slate-800"></div>
        {tooltip}
      </div>
    </div>
  );

  return (
    <div className="flex w-full h-full overflow-hidden bg-slate-50">
      <FilterSidebar 
        data={fullData} 
        filterState={filterState} 
        setFilterState={setFilterState} 
      />
      
      <div className="flex-1 overflow-y-auto p-8 space-y-8 scroll-smooth custom-scrollbar">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <StatCard 
            title="Filtered Sample" 
            value={data.length.toLocaleString()} 
            icon={<Users size={24}/>} 
            color="bg-indigo-600"
            tooltip="The number of patient records currently displayed based on your active search and filter criteria."
          />
          <StatCard 
            title="Primary Trend" 
            value={stats.diagnosisData[0]?.name || 'No Data'} 
            icon={<Activity size={24}/>} 
            color="bg-cyan-500"
            tooltip="The most prevalent clinical diagnosis in this subset. Historically, these often reflect the infectious disease focus of the Haifa Government Hospital."
          />
          <StatCard 
            title="Registry Reach" 
            value={`${stats.timelineData.length} Months`} 
            icon={<Clock size={24}/>} 
            color="bg-amber-500"
            tooltip="The span of the hospital registry currently being viewed, calculated by the distinct months of admission dates."
          />
          <StatCard 
            title="Diversity Index" 
            value={`${stats.religionData.length} Groups`} 
            icon={<Sparkles size={24}/>} 
            color="bg-emerald-500"
            tooltip="A count of the distinct religious or ethnic groups in the filtered sample, illustrating Haifa's multi-cultural demographics in Mandatory Palestine."
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-8">
            <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
              <h3 className="font-bold text-slate-800 mb-6 flex items-center gap-2">
                <TrendingUp size={18} className="text-indigo-600" />
                Admission Timeline (Historical Volume)
              </h3>
              <div className="h-[300px]">
                {stats.timelineData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={stats.timelineData}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                      <XAxis dataKey="name" fontSize={10} axisLine={false} tickLine={false} tickMargin={10} />
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

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
                <h3 className="font-bold text-slate-800 mb-6 flex items-center gap-2">
                  <Activity size={16} className="text-indigo-600" />
                  Top Diagnoses (Prevalence)
                </h3>
                <div className="h-[250px]">
                  {stats.diagnosisData.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie 
                          data={stats.diagnosisData} 
                          innerRadius={50} 
                          outerRadius={75} 
                          paddingAngle={3} 
                          dataKey="value"
                        >
                          {stats.diagnosisData.map((_, index) => <Cell key={`cell-diag-${index}`} fill={COLORS[index % COLORS.length]} />)}
                        </Pie>
                        <Tooltip />
                        <Legend wrapperStyle={{ fontSize: '10px' }} layout="horizontal" verticalAlign="bottom" align="center" />
                      </PieChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="h-full flex items-center justify-center text-slate-400 text-sm">No diagnosis data to display</div>
                  )}
                </div>
              </div>

              <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
                <h3 className="font-bold text-slate-800 mb-6 flex items-center gap-2">
                  <MapPin size={16} className="text-indigo-600" />
                  Catchment Area (Top Cities)
                </h3>
                <div className="h-[250px]">
                  {stats.cityData.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie 
                          data={stats.cityData} 
                          innerRadius={50} 
                          outerRadius={75} 
                          paddingAngle={3} 
                          dataKey="value"
                        >
                          {stats.cityData.map((_, index) => <Cell key={`cell-city-${index}`} fill={COLORS[(index + 3) % COLORS.length]} />)}
                        </Pie>
                        <Tooltip />
                        <Legend wrapperStyle={{ fontSize: '10px' }} layout="horizontal" verticalAlign="bottom" align="center" />
                      </PieChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="h-full flex items-center justify-center text-slate-400 text-sm">No geographical data</div>
                  )}
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-8">
            <div className="bg-indigo-900 text-indigo-100 p-8 rounded-3xl shadow-2xl relative overflow-hidden group min-h-[400px]">
              <div className="absolute top-0 right-0 -m-8 w-48 h-48 bg-indigo-500/10 rounded-full blur-3xl group-hover:bg-indigo-500/20 transition-colors"></div>
              <div className="relative z-10 h-full flex flex-col">
                <div className="flex items-center gap-2 mb-6">
                  <BrainCircuit size={24} className="text-indigo-300" />
                  <h3 className="text-xl font-bold">Smart Analysis</h3>
                </div>
                
                <div className="flex-1 overflow-y-auto pr-2 custom-scrollbar">
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
                        <p className="text-indigo-200/70 leading-relaxed italic text-sm">Analyze historical trends for the current selection based on Haifa's medical history.</p>
                      )}
                    </div>
                  )}
                </div>

                <button 
                  onClick={generateInsights} 
                  disabled={isGenerating || data.length === 0}
                  className="mt-8 w-full py-4 bg-white text-indigo-900 rounded-xl font-bold text-sm hover:bg-indigo-50 transition-all active:scale-[0.98] disabled:opacity-50 shadow-xl"
                >
                  {isGenerating ? 'Synthesizing...' : 'Analyze Cohort'}
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
