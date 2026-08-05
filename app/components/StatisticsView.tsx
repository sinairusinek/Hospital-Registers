
import React, { useMemo, useState, useEffect, useCallback } from 'react';
import {
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, AreaChart, Area, Brush, BarChart, Bar
} from 'recharts';
import { GoogleGenAI } from "@google/genai";
import { TrendingUp, Users, MapPin, HeartPulse, Globe, CheckCircle2, Sparkles, BrainCircuit, Calendar, Baby, Timer, RotateCcw } from 'lucide-react';
import { RegistryRecord, FilterState } from '../types';
import { facetValue, UNKNOWN } from '../facets';
import { buildColorScale, ColorScale, OTHERS, RESIDUE, DIVERGING } from '../colors';
import FilterSidebar from './FilterSidebar';
import HelpPanel, { HelpSection } from './HelpPanel';
import RepresentationPanel from './RepresentationPanel';

const HELP: HelpSection[] = [
  {
    heading: 'Everything here is the selection',
    body: <p>Every chart describes the records currently selected in the filters on the left, not the whole dataset. Narrow the filters and the charts redraw. Clearing the filters returns the full series.</p>
  },
  {
    heading: 'The charts are filters',
    body: <p>Clicking a slice adds that value to the filter for its column, and clicking it again removes it — so the charts can be read against each other. The grey <em>Others</em> slice is a residue of many small values and is not clickable.</p>
  },
  {
    heading: 'The diagnosis chart omits blanks',
    body: <p>Unlike the other charts, the diagnosis chart counts only records with a recorded diagnosis. An unrecorded slice would outweigh every real one and tell you nothing about what patients were treated for. The <em>{UNKNOWN}</em> row in the Diagnosis facet on the left still gives the size of that gap — read the two together, because a diagnosis share is a share of the recorded ones only.</p>
  },
  {
    heading: 'Only eight at a time',
    body: <p>Each pie shows the eight most frequent values and gathers the rest into <em>Others</em>. A long tail of rare values is therefore invisible here by design; the facet list on the left, under <strong>View all</strong>, is where to look for it.</p>
  },
  {
    heading: 'A colour belongs to a value',
    body: <p>Colours are fixed to the values themselves, not to their rank in the current selection, so filtering never repaints the survivors and two states of the same chart can be compared. Muslim is green, Christian orange and Jewish blue in every chart that shows them; <em>{UNKNOWN}</em> is always grey, and the pale grey <em>Others</em> is the residue.</p>
  },
  {
    heading: 'A share on its own compares nothing',
    body: <p>Each legend entry now reads <em>62.4% of 48.1%</em>: the value's share of the current selection, then its share of the whole registry, then the ratio between them. A group can fill most of a diagnosis simply by filling most of the wards, and only the ratio separates the two cases. <strong>×1.00</strong> means the selection mirrors the registry; the ratio appears only once something is filtered, because otherwise it is 1 by construction.</p>
  },
  {
    heading: 'Read the ratio against its interval, and against the year',
    body: <p>The <em>Representation</em> panel gives the same ratio with a 95% confidence interval. A whisker that crosses ×1 is consistent with no difference at all, however striking the bar looks. It also offers to hold admission year constant, which matters here: the registry spans 1930–48, the communities' shares of admissions move a great deal across it, and a ratio computed over the pooled years can be produced entirely by one epidemic coinciding with one year's admission mix. If the crude and the year-held figures disagree, the year-held one is the one to quote.</p>
  },
  {
    heading: 'What the counts are counts of',
    body: <p>These are admissions, not people: the registers carry no patient identifier, so a patient admitted three times counts three times. They are also a record of who reached this hospital and what a clerk wrote down, which is not the same as who was ill in Haifa.</p>
  }
];

interface StatisticsViewProps {
  fullData: RegistryRecord[];
  data: RegistryRecord[];
  filterState: FilterState;
  setFilterState: React.Dispatch<React.SetStateAction<FilterState>>;
}

const TOP_N = 8;

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

  // Built from fullData, so nothing the filters do can repaint a slice.
  const colorScales = useMemo(() => {
    const scales: Record<string, ColorScale> = {};
    ['Sex', 'Result', 'Religion', 'City', 'Nationality', 'Diagnosis'].forEach(name => {
      scales[name] = buildColorScale(fullData, actualKeys[name], name);
    });
    return scales;
  }, [fullData, actualKeys]);

  // The share of the *whole registry* each value carries. Bucketed by exactly
  // the rules the selection charts use — including the diagnosis chart's
  // exclusion of unrecorded rows — so that a slice's share and its baseline are
  // shares of comparable populations and their ratio means something.
  const baselines = useMemo(() => {
    const out: Record<string, Record<string, number>> = {};
    ['Sex', 'Result', 'Religion', 'City', 'Nationality', 'Diagnosis'].forEach(dim => {
      const counts: Record<string, number> = {};
      let total = 0;
      fullData.forEach(row => {
        const v = facetValue(actualKeys[dim] && row[actualKeys[dim]]);
        if (dim === 'Diagnosis' && v === UNKNOWN) return;
        counts[v] = (counts[v] || 0) + 1;
        total++;
      });
      const shares: Record<string, number> = {};
      Object.entries(counts).forEach(([k, n]) => { shares[k] = total > 0 ? n / total : 0; });
      out[dim] = shares;
    });
    return out;
  }, [fullData, actualKeys]);

  // With nothing filtered every ratio is 1 by construction, and printing a
  // column of ×1.00 would suggest a finding where there is only arithmetic.
  const isFiltered = data.length > 0 && data.length < fullData.length;

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
      // Same bucketing rule as the sidebar: a pie slice is clickable and sets a
      // facet filter, so its label has to be a value the filter recognizes.
      const sex = facetValue(actualKeys['Sex'] && row[actualKeys['Sex']]);
      distributions.sex[sex] = (distributions.sex[sex] || 0) + 1;

      const res = facetValue(actualKeys['Result'] && row[actualKeys['Result']]);
      distributions.result[res] = (distributions.result[res] || 0) + 1;

      const rel = facetValue(actualKeys['Religion'] && row[actualKeys['Religion']]);
      distributions.religion[rel] = (distributions.religion[rel] || 0) + 1;

      const city = facetValue(actualKeys['City'] && row[actualKeys['City']]);
      distributions.city[city] = (distributions.city[city] || 0) + 1;

      const nat = facetValue(actualKeys['Nationality'] && row[actualKeys['Nationality']]);
      distributions.nationality[nat] = (distributions.nationality[nat] || 0) + 1;

      // The diagnosis chart stays a distribution of recorded diagnoses only: an
      // unrecorded slice would outweigh every real one. The sidebar still counts
      // them, so the size of the gap remains visible there.
      const diag = facetValue(actualKeys['Diagnosis'] && row[actualKeys['Diagnosis']]);
      if (diag !== UNKNOWN) {
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
    if (!entry || entry.name === OTHERS) return;
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

  const renderPie = (chartData: any[], displayName: string) => {
    if (chartData.length === 0) return <div className="h-full flex items-center justify-center text-slate-400 text-sm italic">No data</div>;
    const color = colorScales[displayName];
    const base = baselines[displayName] || {};
    const top = chartData.slice(0, TOP_N);
    const othersValue = chartData.slice(TOP_N).reduce((acc, curr) => acc + curr.value, 0);
    const finalData = othersValue > 0 ? [...top, { name: OTHERS, value: othersValue }] : top;
    // The share is of this chart's own total: the diagnosis chart drops the
    // unrecorded rows, so measuring against the whole selection would quietly
    // shrink every diagnosis.
    const total = finalData.reduce((acc, curr) => acc + curr.value, 0) || 1;
    // recharts 3 ignores a custom Legend `payload`, so the legend is rendered
    // here: in count order, with the share each slice carries, which is what
    // makes the pies readable at this size.
    return (
      <div className="h-full flex flex-col">
        <div className="flex-1 min-h-0">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={finalData} innerRadius={50} outerRadius={75} paddingAngle={3} dataKey="value" animationDuration={800} onClick={(entry) => handlePieClick(displayName, entry)} className="cursor-pointer outline-none">
            {finalData.map((entry) => (
              <Cell key={`cell-${displayName}-${entry.name}`} fill={color ? color(entry.name) : RESIDUE} className="hover:opacity-80 transition-opacity" />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}
            content={({ active, payload }: any) => {
              if (!active || !payload?.length) return null;
              const entry = payload[0].payload;
              const share = entry.value / total;
              const baseShare = base[entry.name];
              return (
                <div className="bg-white rounded-xl shadow-lg border border-slate-200 p-3 text-[11px] space-y-1">
                  <div className="font-bold text-slate-800">{entry.name}</div>
                  <div className="text-slate-500">{entry.value.toLocaleString()} records · {(share * 100).toFixed(1)}% of this selection</div>
                  {entry.name !== OTHERS && baseShare !== undefined && (
                    <div className="text-slate-500">{(baseShare * 100).toFixed(1)}% of the whole registry</div>
                  )}
                  {isFiltered && entry.name !== OTHERS && baseShare ? (
                    <div className="pt-1 border-t border-slate-100 font-bold text-slate-700">
                      ×{(share / baseShare).toFixed(2)} representation
                    </div>
                  ) : null}
                </div>
              );
            }}
          />
        </PieChart>
      </ResponsiveContainer>
        </div>
        {/* Beside each slice's share of the selection sits its share of the whole
            registry, because the first number alone answers no comparative
            question: a group can dominate a diagnosis simply by dominating the
            wards. The ratio of the two is what a claim would rest on. */}
        <ul className="flex flex-wrap justify-center gap-x-3 gap-y-1 pt-3 text-[9px] text-slate-600">
          {finalData.map(entry => {
            const share = entry.value / total;
            const baseShare = base[entry.name];
            const lift = isFiltered && entry.name !== OTHERS && baseShare ? share / baseShare : null;
            return (
              <li key={`legend-${displayName}-${entry.name}`} className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: color ? color(entry.name) : RESIDUE }} />
                <span className={entry.name === OTHERS ? 'italic text-slate-400' : ''}>
                  {entry.name} ({(share * 100).toFixed(1)}%)
                  {baseShare !== undefined && entry.name !== OTHERS && (
                    <span className="text-slate-400"> of {(baseShare * 100).toFixed(1)}%</span>
                  )}
                </span>
                {lift !== null && (
                  <span
                    className="font-bold tabular-nums"
                    style={{ color: lift >= 1 ? DIVERGING.above : DIVERGING.below }}
                  >
                    ×{lift.toFixed(2)}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      </div>
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

        <RepresentationPanel
          fullData={fullData}
          data={data}
          actualKeys={actualKeys}
          filterState={filterState}
        />

        {/* Charts Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {/* Categorical Pies */}
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm"><h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2"><HeartPulse size={18} className="text-rose-500" /> Diagnoses</h3><div className="h-[300px]">{renderPie(stats.diagnosisData, "Diagnosis")}</div></div>
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm"><h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2"><CheckCircle2 size={18} className="text-emerald-500" /> Clinical Result</h3><div className="h-[300px]">{renderPie(stats.resultData, "Result")}</div></div>
          
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

          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm"><h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2"><Sparkles size={18} className="text-amber-500" /> Religion</h3><div className="h-[300px]">{renderPie(stats.religionData, "Religion")}</div></div>
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm"><h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2"><Globe size={18} className="text-emerald-500" /> Nationality</h3><div className="h-[300px]">{renderPie(stats.nationalityData, "Nationality")}</div></div>
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm"><h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2"><Users size={18} className="text-indigo-500" /> Sex Distribution</h3><div className="h-[300px]">{renderPie(stats.sexData, "Sex")}</div></div>
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm"><h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2"><MapPin size={18} className="text-slate-500" /> Origin Cities</h3><div className="h-[300px]">{renderPie(stats.cityData, "City")}</div></div>
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

      <HelpPanel title="How to read this" sections={HELP} storageKey="help.statistics" />
    </div>
  );
};

export default StatisticsView;
