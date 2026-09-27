import React, { useEffect, useMemo, useState } from 'react';
import { Loader2, AlertTriangle, Table2 } from 'lucide-react';
import HelpPanel, { HelpSection } from './HelpPanel';
import { SERIES, NEUTRAL, RESIDUE } from '../colors';

/**
 * Was the Government Hospital a common space for Arabs, Jews and Britons?
 *
 * The view answers from two sides that disagree productively. The 1936 Schedule
 * of Accommodation designed exactly one group-specific unit — the 24-bed British
 * Section — and cut everything else by sex, function and *class*. The register
 * then shows the medical wards genuinely mixed, page by page. So the segregation
 * that existed ran along nationality and class, not confession.
 *
 * Every number comes from pipeline/shared_space_figures.py; this file holds
 * layout and argument, never arithmetic, so a recompute cannot leave the prose
 * behind. Where a figure is weak the view says so next to it rather than in a
 * footnote — the ward column's late-period gaps are the case that matters.
 */

const DATA_URL = `${import.meta.env.BASE_URL}data/shared-space.json`;

// ---------------------------------------------------------------- types

interface WardRow { ward: string; n: number; Muslim: number; Christian: number; Jewish: number; }
interface Adjacency { ward: string; n: number; observed: number; chance: number; excess: number; }
interface MixedRow {
  group: string; n: number; classN: number;
  class1: number; class2: number; class3: number;
  cfr: number; cfrN: number; cfrThirdClass: number | null; cfrThirdClassN: number;
}
interface YearRow {
  year: string; n: number; Muslim: number; Christian: number; Jewish: number;
  isolationN: number; jewishInIsolation: number | null;
}
interface Occupancy {
  year: string; admissions: number; bedDays: number; meanBeds: number; pctOf24: number;
}
interface Named { name: string; n: number; }
interface SharedSpaceData {
  meta: { records: number; note: string };
  wardMix: { wards: WardRow[]; baseline: WardRow };
  mixing: {
    pages: {
      n: number; allThree: number; allThreePct: number;
      two: number; twoPct: number; single: number; singlePct: number;
    };
    adjacency: Adjacency[];
  };
  britishSection: {
    total: number; designedBeds: number;
    religion: Named[]; nationality: Named[];
    nonBritish: {
      n: number; byClass: Record<string, number>; byReligion: Record<string, number>;
      staff: number; topOccupations: Named[];
    };
    occupancy: Occupancy[];
    reach: { group: string; n: number; pct: number }[];
  };
  mixedGroups: { mixed: MixedRow[]; plain: MixedRow[] };
  withdrawal: {
    years: YearRow[];
    lateMonths: { month: string; Muslim: number; Christian: number; Jewish: number; n: number }[];
  };
  staff: {
    n: number; female: number; inBritishSection: number;
    comparison: { religion: string; staffPct: number; staffN: number; allPct: number }[];
    wards: Named[]; occupations: Named[];
  };
  gaps: {
    coverage: { column: string; filled: number; pct: number }[];
    byYear: { year: string; n: number; icd9Missing: number; wardMissing: number; resultMissing: number }[];
    byGroup: { group: string; n: number; icd9Missing: number; wardMissing: number; resultMissing: number }[];
    wardMissingLate: Record<string, string | number | null>[];
    wardBias: Record<string, Record<string, number>>;
  };
  payment: {
    evidence: {
      blankWithRatePct: number; gratisWithRatePct: number;
      blankByClass: Record<string, number>;
      pages: { n: number; allBlankPct: number; noneBlankPct: number; mixedPct: number };
      split: { gratis: number; chargedWithRate: number; unknown: number };
    };
    byGroup: {
      group: string; n: number; gratisPct: number; gratisThirdClassPct: number;
      thirdClassN: number; medianRate: number | null; rateN: number;
    }[];
    byClass: Record<string, string | number | null>[];
    byMixed: {
      group: string; n: number; gratisPct: number;
      gratisThirdClassPct: number; thirdClassN: number;
    }[];
  };
}

// ---------------------------------------------------------------- colour

// The three religions keep the colours they carry everywhere else in the site
// and in the article's figures: Muslim green, Christian orange, Jewish blue.
const REL = { Muslim: SERIES[2], Christian: SERIES[1], Jewish: SERIES[0] } as const;
const MCJ = ['Muslim', 'Christian', 'Jewish'] as const;

// The mixed grouping splits two of those three, so each half needs a hue that
// still reads as its parent. #a8481a is a darker orange for the British
// Christians and violet a cooler partner for the non-Palestinian Jewish rows;
// both were validated against the other four for CVD separation (worst adjacent
// pair ΔE 9.2 deutan, 15.4 normal) before being used.
const MIXED: Record<string, string> = {
  'Muslim': SERIES[2],
  'Christian, Palestinian nat.': SERIES[1],
  'Christian, British nat.': '#a8481a',
  'Jewish, Palestinian nat.': SERIES[0],
  'Jewish, other/unrecorded nat.': SERIES[6]
};

// Short labels for the axis; the legend and the table carry the full ones.
const SHORT: Record<string, string> = {
  'Muslim': 'Muslim',
  'Christian, Palestinian nat.': 'Christian, Palestinian',
  'Christian, British nat.': 'Christian, British',
  'Jewish, Palestinian nat.': 'Jewish, Palestinian',
  'Jewish, other/unrecorded nat.': 'Jewish, other nat.'
};

// ---------------------------------------------------------------- help

const HELP: HelpSection[] = [
  {
    heading: 'What this view argues',
    body: (
      <p>
        That the hospital's one designed partition was <em>national</em>, not confessional. The
        1936 Schedule of Accommodation lays out 277 beds and exactly one group-specific unit — the
        24-bed British Section. There is no Arab ward and no Jewish ward anywhere in the plan; the
        medical blocks divide by sex and function, and the Maternity Section divides by class.
        The register then shows those wards genuinely mixed. Read the two together: the building
        and the ledger are independent sources that happen to agree.
      </p>
    )
  },
  {
    heading: 'How mixing is measured',
    body: (
      <p>
        Two ways, because neither alone is enough. The <strong>ledger-page test</strong> asks how
        many religions share a register page — the register was kept in strict admission order, so
        a page is a slice of real time rather than a category. The <strong>adjacency test</strong>{' '}
        asks whether consecutive admissions to the same ward share a religion more often than that
        ward's own composition would produce by chance (the null is the sum of squared shares). A
        ward that sorted its patients would sit far above its chance line. Only one does.
      </p>
    )
  },
  {
    heading: 'Why religion is crossed with nationality',
    body: (
      <p>
        Because the undifferentiated <em>Christian</em> category is an artefact: it pools British
        officials with Palestinian Arabs and so invents a prosperous Christian population that did
        not exist. Split by nationality, second class is 83.5% of the British Christians and 21.6%
        of the Palestinian ones. Any comparison that leaves the category whole is measuring the
        colonial administration and calling it a religion.
      </p>
    )
  },
  {
    heading: 'Where the record is weak',
    body: (
      <p>
        The ward column is blank for about one admission in six, and the blanks are concentrated in
        the register's last years — not spread evenly. They also fall unevenly by group there: in
        1947 the ward is missing for 33% of Muslim admissions and 58% of Jewish ones. Ward shares
        for 1944–48 are therefore the weakest numbers in this view, and the Isolation label all but
        disappears from the column after 1940, so no late comparison is possible for it. The gaps
        panel gives the full profile.
      </p>
    )
  },
  {
    heading: 'The payment column is a gratis marker',
    body: (
      <p>
        It is not a "recorded / not recorded" field, and reading it as one inverts the finding. The
        clerk wrote <em>Gratis</em> when treatment was free and left the cell <strong>empty</strong>{' '}
        when a fee was charged, entering the fee in the Rate column instead. Rate is filled for 56%
        of the blank rows and 0.6% of the Gratis ones; the blank covers 99% of first class and 20%
        of third; and 89% of pages mix blank with filled rows, so it is not a clerk skipping a
        column. A blank is therefore evidence of payment. The 13% of admissions that are blank{' '}
        <em>and</em> carry no rate are the genuinely unknown ones.
      </p>
    )
  },
  {
    heading: 'Denominators',
    body: (
      <p>
        Religion shares use an M+C+J denominator: the 78 admissions recorded as Bahai, Druze, Arab
        or unparseable leave both numerator and denominator rather than forming a category. Class
        percentages use every row with a recorded class. Case-fatality is deaths over admissions
        with a recorded result. Notebook 25 — the Atlit camp register, 965 rows, 962 of them
        Jewish — is excluded throughout, as everywhere else in the project.
      </p>
    )
  }
];

// ---------------------------------------------------------------- pieces

const Section: React.FC<{
  n: string; title: string; lede: React.ReactNode; children: React.ReactNode;
}> = ({ n, title, lede, children }) => (
  <section className="mb-14">
    <div className="flex items-baseline gap-3 mb-2">
      <span className="text-xs font-mono text-slate-400 tabular-nums">{n}</span>
      <h2 className="text-xl font-bold text-slate-800 tracking-tight">{title}</h2>
    </div>
    <div className="text-sm text-slate-600 leading-relaxed max-w-3xl mb-6">{lede}</div>
    {children}
  </section>
);

/** A caution that belongs beside a figure, not in a footnote. */
const Caveat: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <p className="flex gap-2 text-xs text-amber-800 bg-amber-50 border border-amber-200
                rounded-lg px-3 py-2 mt-3 max-w-3xl">
    <AlertTriangle size={14} className="shrink-0 mt-0.5" aria-hidden="true" />
    <span className="leading-relaxed">{children}</span>
  </p>
);

const Legend: React.FC<{ items: { label: string; color: string }[] }> = ({ items }) => (
  <ul className="flex flex-wrap gap-x-5 gap-y-1.5 mb-4">
    {items.map(i => (
      <li key={i.label} className="flex items-center gap-2 text-xs text-slate-600">
        <span className="w-3 h-3 rounded-sm shrink-0" style={{ background: i.color }} aria-hidden="true" />
        {i.label}
      </li>
    ))}
  </ul>
);

/**
 * A 100% stacked bar. Segments are separated by a 2px surface gap so adjacent
 * fills never read as one, and every segment carries its own number — the
 * project's green sits below 3:1 against white, so identity is never left to
 * colour alone.
 */
const StackedBar: React.FC<{
  label: string; sub?: string; parts: { key: string; pct: number; color: string }[];
  emphasis?: boolean;
}> = ({ label, sub, parts, emphasis }) => (
  <div className={`grid grid-cols-[13rem_1fr] gap-4 items-center py-1.5
                   ${emphasis ? 'font-semibold' : ''}`}>
    <div className="text-right">
      <div className={`text-sm ${emphasis ? 'text-slate-900' : 'text-slate-700'}`}>{label}</div>
      {sub && <div className="text-[11px] text-slate-400 tabular-nums">{sub}</div>}
    </div>
    <div className="flex h-7 gap-[2px]" role="img"
         aria-label={parts.map(p => `${p.key} ${p.pct}%`).join(', ')}>
      {parts.filter(p => p.pct > 0).map(p => (
        <div key={p.key} className="flex items-center justify-center overflow-hidden
                                    first:rounded-l last:rounded-r"
             style={{ width: `${p.pct}%`, background: p.color }}
             title={`${p.key}: ${p.pct}%`}>
          {p.pct >= 7 && (
            <span className="text-[11px] font-medium text-white tabular-nums px-1">
              {Math.round(p.pct)}%
            </span>
          )}
        </div>
      ))}
    </div>
  </div>
);

/** Every figure ships a table view; this is the disclosure that holds it. */
const TableView: React.FC<{ children: React.ReactNode; label?: string }> = ({ children, label }) => (
  <details className="mt-4 max-w-3xl group">
    <summary className="flex items-center gap-1.5 text-xs text-slate-500 cursor-pointer
                        hover:text-slate-700 w-fit">
      <Table2 size={13} aria-hidden="true" />
      {label || 'Table view'}
    </summary>
    <div className="mt-3 overflow-x-auto">{children}</div>
  </details>
);

const Num: React.FC<{ v: number | null | undefined; suffix?: string; dp?: number }> =
  ({ v, suffix = '', dp = 1 }) => (
    <span className="tabular-nums">
      {v === null || v === undefined ? '—' : `${v.toFixed(dp)}${suffix}`}
    </span>
  );

const TH: React.FC<{ children: React.ReactNode; right?: boolean }> = ({ children, right }) => (
  <th className={`px-3 py-1.5 font-semibold text-slate-600 border-b border-slate-200
                  ${right ? 'text-right' : 'text-left'}`}>{children}</th>
);
const TD: React.FC<{ children: React.ReactNode; right?: boolean }> = ({ children, right }) => (
  <td className={`px-3 py-1.5 border-b border-slate-100 ${right ? 'text-right tabular-nums' : ''}`}>
    {children}
  </td>
);

/** A headline number that is the chart, because one number is not a bar chart. */
const Stat: React.FC<{ value: string; label: string; note?: string }> = ({ value, label, note }) => (
  <div className="bg-white rounded-xl border border-slate-200 px-5 py-4">
    <div className="text-3xl font-bold text-slate-800 tabular-nums tracking-tight">{value}</div>
    <div className="text-sm text-slate-600 mt-0.5">{label}</div>
    {note && <div className="text-xs text-slate-400 mt-1 leading-snug">{note}</div>}
  </div>
);

// ---------------------------------------------------------------- view

const SharedSpaceView: React.FC = () => {
  const [data, setData] = useState<SharedSpaceData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    fetch(DATA_URL)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(d => { if (live) setData(d); })
      .catch(e => { if (live) setError(String(e.message || e)); });
    return () => { live = false; };
  }, []);

  // The adjacency chart's scale: the largest excess sets the bar width, so the
  // British Section's outlier is read against the others rather than clipped.
  const maxExcess = useMemo(
    () => data ? Math.max(...data.mixing.adjacency.map(a => a.excess)) : 1,
    [data]
  );

  // The CFR bars are scaled to the worst rate in the data rather than to a fixed
  // ceiling, so a recompute cannot silently push a bar past its track.
  const maxCfr = useMemo(
    () => data ? Math.max(...data.mixedGroups.mixed.map(m => m.cfr)) : 1,
    [data]
  );

  if (error) {
    return (
      <div className="h-full overflow-y-auto p-8">
        <div className="max-w-2xl mx-auto bg-amber-50 border border-amber-200 rounded-xl p-6">
          <h2 className="font-bold text-slate-800 mb-2">The shared-space figures are not built yet</h2>
          <p className="text-sm text-slate-600 leading-relaxed">
            This view reads <code className="text-xs bg-white px-1 py-0.5 rounded border
            border-amber-200">data/shared-space.json</code>, which the site stages from the
            repository. Build it with:
          </p>
          <pre className="mt-3 text-xs bg-white border border-amber-200 rounded p-3 overflow-x-auto">
python3 pipeline/shared_space_figures.py</pre>
          <p className="text-xs text-slate-500 mt-3">Fetch failed: {error}</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="h-full flex items-center justify-center text-slate-500 gap-2">
        <Loader2 size={18} className="animate-spin" aria-hidden="true" />
        Loading the shared-space figures…
      </div>
    );
  }

  const { wardMix, mixing, britishSection: bs, mixedGroups, withdrawal, staff, gaps, payment } = data;
  const relLegend = MCJ.map(m => ({ label: m, color: REL[m] }));
  const brit = mixedGroups.plain.find(p => p.group === 'Christian');
  const britMixed = mixedGroups.mixed.find(m => m.group === 'Christian, British nat.');
  const palMixed = mixedGroups.mixed.find(m => m.group === 'Christian, Palestinian nat.');

  return (
    // A flex row, so the help sits beside the figures as a foldable side panel
    // rather than as a block the reader must scroll past to reach section 01.
    // The article column owns the scrollbar; the panel keeps its own.
    <div className="flex w-full h-full overflow-hidden bg-slate-50">
      <div className="flex-1 min-w-0 overflow-y-auto custom-scrollbar">
        <div className="max-w-5xl mx-auto px-8 py-10">
        <header className="mb-8 max-w-3xl">
          <p className="text-xs font-semibold uppercase tracking-wider text-indigo-600 mb-2">
            Figures for the article
          </p>
          <h1 className="text-3xl font-bold text-slate-900 tracking-tight mb-3">
            One hospital, three publics
          </h1>
          <p className="text-slate-600 leading-relaxed">
            Whether the Government Hospital at Haifa was a space Arabs, Jews and Britons actually
            shared — and along which line it was divided when it was. The short answer, from the
            building's own plan and from {data.meta.records.toLocaleString()} admissions: the one
            designed partition was national and the working partition was class. Confession did not
            sort the wards.
          </p>
        </header>

        {/* ---------------------------------------------------------- 01 */}
        <Section
          n="01"
          title="The wards were mixed; one was not"
          lede={
            <p>
              Ward composition against the hospital's own baseline. Every medical ward carries all
              three groups in numbers, and their shares track what each ward treated — Isolation
              skews Jewish because notifiable infectious disease was reported and admitted, Surgical
              skews Muslim because the rural referral catchment did. The British Section is the only
              ward whose composition is a fact about who the patients <em>were</em> rather than what
              they had.
            </p>
          }
        >
          <Legend items={relLegend} />
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            {wardMix.wards.map(w => (
              <StackedBar
                key={w.ward} label={w.ward} sub={`n=${w.n.toLocaleString()}`}
                parts={MCJ.map(m => ({ key: m, pct: w[m], color: REL[m] }))}
              />
            ))}
            <div className="border-t border-slate-200 mt-3 pt-3">
              <StackedBar
                emphasis label={wardMix.baseline.ward}
                sub={`n=${wardMix.baseline.n.toLocaleString()}`}
                parts={MCJ.map(m => ({ key: m, pct: wardMix.baseline[m], color: REL[m] }))}
              />
            </div>
          </div>
          <Caveat>
            Ward is blank for roughly one admission in six, and the blanks cluster in the register's
            last years rather than spreading evenly — so these shares describe the period up to 1940
            far better than the period after it. The Isolation label itself all but leaves the column
            after 1940.
          </Caveat>
          <TableView>
            <table className="w-full text-xs border-collapse">
              <thead><tr><TH>Ward</TH><TH right>n</TH>
                {MCJ.map(m => <TH key={m} right>{m}</TH>)}</tr></thead>
              <tbody>
                {[...wardMix.wards, wardMix.baseline].map(w => (
                  <tr key={w.ward}>
                    <TD>{w.ward}</TD><TD right>{w.n.toLocaleString()}</TD>
                    {MCJ.map(m => <TD key={m} right><Num v={w[m]} suffix="%" /></TD>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </TableView>
        </Section>

        {/* ---------------------------------------------------------- 02 */}
        <Section
          n="02"
          title="The ledger did not sort its patients"
          lede={
            <p>
              If the hospital had grouped admissions by community, the register would show it: pages
              would run in confessional blocks and a patient's neighbour in a ward would share their
              religion more often than chance allows. Neither happens. The register was kept in
              strict admission order, and it reads as a queue rather than a sorting.
            </p>
          }
        >
          <div className="grid sm:grid-cols-3 gap-4 mb-6">
            <Stat value={`${mixing.pages.allThreePct}%`}
                  label="of ledger pages carry all three religions"
                  note={`${mixing.pages.allThree.toLocaleString()} of ${mixing.pages.n.toLocaleString()} pages with 8+ entries`} />
            <Stat value={`${mixing.pages.singlePct}%`}
                  label="carry only one"
                  note={`${mixing.pages.single} pages — the exceptions, not the rule`} />
            <Stat value={`+${mixing.adjacency.find(a => a.ward === 'British Section')?.excess ?? 0}`}
                  label="pts of same-religion clustering, British Section"
                  note="every other ward sits within 4.3 points of chance" />
          </div>

          <h3 className="text-sm font-semibold text-slate-700 mb-1">
            Same-religion neighbour, against chance
          </h3>
          <p className="text-xs text-slate-500 mb-4 max-w-3xl">
            Bars show the excess over each ward's own expected rate. A ward that placed patients by
            community would stand well clear of the rest; one ward does.
          </p>
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            {mixing.adjacency.map(a => {
              const outlier = a.ward === 'British Section';
              return (
                <div key={a.ward} className="grid grid-cols-[13rem_1fr_5rem] gap-4 items-center py-1.5">
                  <div className="text-right text-sm text-slate-700">{a.ward}</div>
                  <div className="h-6 bg-slate-100 rounded-sm relative overflow-hidden">
                    <div className="h-full rounded-sm"
                         style={{ width: `${Math.max(2, (a.excess / maxExcess) * 100)}%`,
                                  background: outlier ? SERIES[7] : NEUTRAL }} />
                  </div>
                  <div className="text-xs text-slate-500 tabular-nums">
                    {a.observed}% <span className="text-slate-300">/</span> {a.chance}%
                  </div>
                </div>
              );
            })}
            <p className="text-[11px] text-slate-400 mt-3 pl-[14rem]">
              observed <span className="text-slate-300">/</span> expected by chance
            </p>
          </div>
          <TableView>
            <table className="w-full text-xs border-collapse">
              <thead><tr><TH>Ward</TH><TH right>n</TH><TH right>Observed</TH>
                <TH right>Chance</TH><TH right>Excess</TH></tr></thead>
              <tbody>
                {mixing.adjacency.map(a => (
                  <tr key={a.ward}>
                    <TD>{a.ward}</TD><TD right>{a.n.toLocaleString()}</TD>
                    <TD right><Num v={a.observed} suffix="%" /></TD>
                    <TD right><Num v={a.chance} suffix="%" /></TD>
                    <TD right>{a.excess > 0 ? '+' : ''}<Num v={a.excess} /></TD>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableView>
        </Section>

        {/* ---------------------------------------------------------- 03 */}
        <Section
          n="03"
          title="The one segregated ward, and how it leaked"
          lede={
            <p>
              The British Section was designed for {bs.designedBeds} beds, and the 1935 memorandum
              says plainly what for: "the increase of British Officials, Police and Residents for the
              hospitalisation of whom no adequate facilities exist". It is the hospital's only
              national enclosure — and it was never sealed.{' '}
              {bs.nonBritish.n.toLocaleString()} of its {bs.total.toLocaleString()} admissions were
              not British nationals at all, including {bs.nonBritish.byReligion.Muslim} Muslims and{' '}
              {bs.nonBritish.byReligion.Jewish} Jews. They were not admitted as fee-paying
              equivalents: {bs.nonBritish.byClass['3']} of them were third class. Where an
              occupation is recorded it is overwhelmingly the hospital's own nursing staff — and the
              ward ran at well under half its designed capacity, which is how there was room.
            </p>
          }
        >
          <div className="grid sm:grid-cols-3 gap-4 mb-6">
            <Stat value={bs.total.toLocaleString()} label="admissions to the British Section"
                  note={`${bs.designedBeds} beds in the 1936 schedule`} />
            <Stat value={`${Math.max(...bs.occupancy.map(o => o.pctOf24))}%`}
                  label="peak mean occupancy of those beds"
                  note="1944, the fullest year in the register" />
            <Stat value={bs.nonBritish.n.toLocaleString()} label="admissions of non-British nationals"
                  note={`${bs.nonBritish.staff} carry a nursing or medical title`} />
          </div>

          <div className="grid lg:grid-cols-2 gap-5">
            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <h3 className="text-sm font-semibold text-slate-700 mb-1">
                Mean beds occupied, against 24 designed
              </h3>
              <p className="text-xs text-slate-500 mb-4">
                Bed-days over 365. Part-covered years (1940, 1948) are low because the register
                covers only part of them, not because the ward emptied.
              </p>
              {bs.occupancy.map(o => (
                <div key={o.year} className="grid grid-cols-[3rem_1fr_6.5rem] gap-3 items-center py-1">
                  <div className="text-xs text-slate-500 tabular-nums">{o.year}</div>
                  <div className="h-5 bg-slate-100 rounded-sm overflow-hidden">
                    <div className="h-full rounded-sm"
                         style={{ width: `${Math.min(100, o.pctOf24)}%`, background: '#a8481a' }} />
                  </div>
                  <div className="text-xs text-slate-500 tabular-nums">
                    {o.meanBeds} beds · {o.pctOf24}%
                  </div>
                </div>
              ))}
            </div>

            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <h3 className="text-sm font-semibold text-slate-700 mb-1">
                Who reached the British Section
              </h3>
              <p className="text-xs text-slate-500 mb-4">
                Share of each group's ward-known admissions that went to it. British-national
                Christians are the ward's population; everyone else gets in at the margin — except
                Palestinian Jews, at nearly three times the rate of Muslims and Palestinian
                Christians, which the nursing corps explains.
              </p>
              {bs.reach.map(r => (
                <div key={r.group} className="grid grid-cols-[10rem_1fr_3.5rem] gap-3 items-center py-1">
                  <div className="text-xs text-slate-600 text-right leading-tight">
                    {SHORT[r.group] ?? r.group}
                  </div>
                  <div className="h-5 bg-slate-100 rounded-sm overflow-hidden">
                    <div className="h-full rounded-sm"
                         style={{ width: `${r.pct}%`, background: MIXED[r.group] ?? NEUTRAL }} />
                  </div>
                  <div className="text-xs text-slate-500 tabular-nums">{r.pct}%</div>
                </div>
              ))}
            </div>
          </div>

          <TableView label="Occupations recorded for non-British admissions">
            <table className="w-full text-xs border-collapse">
              <thead><tr><TH>Occupation as written</TH><TH right>n</TH></tr></thead>
              <tbody>
                {bs.nonBritish.topOccupations.map(o => (
                  <tr key={o.name}><TD>{o.name}</TD><TD right>{o.n}</TD></tr>
                ))}
              </tbody>
            </table>
            <p className="text-[11px] text-slate-400 mt-2">
              Occupation is recorded for a minority of these admissions; the titles that are
              recorded are almost all nursing.
            </p>
          </TableView>
        </Section>

        {/* ---------------------------------------------------------- 04 */}
        <Section
          n="04"
          title="'Christian' is not a category"
          lede={
            <p>
              Left whole, Christians look like the hospital's prosperous middle:{' '}
              <Num v={brit?.class2} suffix="%" /> of them in second class, against{' '}
              <Num v={mixedGroups.plain.find(p => p.group === 'Muslim')?.class2} suffix="%" /> of
              Muslims. Cross religion with nationality and the appearance dissolves. Second class is{' '}
              <Num v={britMixed?.class2} suffix="%" /> of the British-national Christians and{' '}
              <Num v={palMixed?.class2} suffix="%" /> of the Palestinian ones — the prosperity was
              the colonial officialdom, not an Arab Christian bourgeoisie. The same split moves
              mortality: the undifferentiated Christian rate of <Num v={brit?.cfr} suffix="%" dp={2} />{' '}
              is a blend of <Num v={britMixed?.cfr} suffix="%" dp={2} /> and{' '}
              <Num v={palMixed?.cfr} suffix="%" dp={2} />.
            </p>
          }
        >
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Class, undifferentiated</h3>
          <div className="bg-white rounded-xl border border-slate-200 p-5 mb-5">
            {mixedGroups.plain.map(r => (
              <StackedBar key={r.group} label={r.group} sub={`n=${r.classN.toLocaleString()}`}
                parts={[
                  { key: 'First class', pct: r.class1, color: SERIES[3] },
                  { key: 'Second class', pct: r.class2, color: SERIES[4] },
                  { key: 'Third class', pct: r.class3, color: NEUTRAL }
                ]} />
            ))}
          </div>

          <h3 className="text-sm font-semibold text-slate-700 mb-3">
            Class, with nationality crossed in
          </h3>
          <Legend items={[
            { label: 'First class', color: SERIES[3] },
            { label: 'Second class', color: SERIES[4] },
            { label: 'Third class', color: NEUTRAL }
          ]} />
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            {mixedGroups.mixed.map(r => (
              <StackedBar key={r.group} label={SHORT[r.group] ?? r.group}
                sub={`n=${r.classN.toLocaleString()}`}
                parts={[
                  { key: 'First class', pct: r.class1, color: SERIES[3] },
                  { key: 'Second class', pct: r.class2, color: SERIES[4] },
                  { key: 'Third class', pct: r.class3, color: NEUTRAL }
                ]} />
            ))}
          </div>

          <h3 className="text-sm font-semibold text-slate-700 mt-8 mb-1">
            Case-fatality by the crossed grouping
          </h3>
          <p className="text-xs text-slate-500 mb-4 max-w-3xl">
            Deaths over admissions with a recorded result. The third-class column is the one that
            matters, because it compares people the hospital charged the same: the Muslim excess
            survives it, and the Christian advantage largely does not.
          </p>
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            {mixedGroups.mixed.map(r => (
              <div key={r.group} className="grid grid-cols-[12rem_1fr_9rem] gap-4 items-center py-1.5">
                <div className="text-right text-sm text-slate-700 leading-tight">
                  {SHORT[r.group] ?? r.group}
                </div>
                <div className="h-6 bg-slate-100 rounded-sm overflow-hidden">
                  <div className="h-full rounded-sm"
                       style={{ width: `${(r.cfr / maxCfr) * 100}%`,
                                background: MIXED[r.group] ?? NEUTRAL }} />
                </div>
                <div className="text-xs text-slate-500 tabular-nums">
                  <Num v={r.cfr} suffix="%" dp={2} />
                  <span className="text-slate-300"> · 3rd </span>
                  {r.cfrThirdClass === null
                    ? <span className="text-slate-300">n/a</span>
                    : <Num v={r.cfrThirdClass} suffix="%" dp={2} />}
                </div>
              </div>
            ))}
          </div>
          <Caveat>
            British-national Christians are absent from third class by construction — 49 admissions —
            so no third-class rate is reported for them. Their overall advantage is a class effect
            and a age-and-diagnosis effect, not evidence about care inside a shared ward.
          </Caveat>
          <TableView>
            <table className="w-full text-xs border-collapse">
              <thead><tr><TH>Group</TH><TH right>n</TH><TH right>1st</TH><TH right>2nd</TH>
                <TH right>3rd</TH><TH right>CFR</TH><TH right>CFR, 3rd class</TH></tr></thead>
              <tbody>
                {mixedGroups.mixed.map(r => (
                  <tr key={r.group}>
                    <TD>{r.group}</TD><TD right>{r.n.toLocaleString()}</TD>
                    <TD right><Num v={r.class1} suffix="%" /></TD>
                    <TD right><Num v={r.class2} suffix="%" /></TD>
                    <TD right><Num v={r.class3} suffix="%" /></TD>
                    <TD right><Num v={r.cfr} suffix="%" dp={2} /></TD>
                    <TD right>{r.cfrThirdClass === null ? '—'
                      : <><Num v={r.cfrThirdClass} suffix="%" dp={2} />
                          <span className="text-slate-400"> (n={r.cfrThirdClassN.toLocaleString()})</span></>}</TD>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableView>
        </Section>

        {/* ---------------------------------------------------------- 05 */}
        <Section
          n="05"
          title="One community left"
          lede={
            <p>
              The Jewish share of admissions falls from{' '}
              <Num v={withdrawal.years[0]?.Jewish} suffix="%" /> in {withdrawal.years[0]?.year} to{' '}
              <Num v={withdrawal.years[withdrawal.years.length - 1]?.Jewish} suffix="%" /> in 1948.
              The turn is 1936–37, not 1947: a decade before the war, and contemporaneous with the
              Arab Revolt and the build-out of separate Jewish provision in Haifa. While the
              Isolation ward is still recorded, Jewish patients hold near half of it even as their
              overall share halves — compulsory notification did not let them leave. What collapsed
              first was elective use of a shared institution.
            </p>
          }
        >
          <Legend items={relLegend} />
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            {withdrawal.years.map(y => (
              <StackedBar key={y.year} label={y.year} sub={`n=${y.n.toLocaleString()}`}
                parts={MCJ.map(m => ({ key: m, pct: y[m], color: REL[m] }))} />
            ))}
          </div>
          <p className="text-xs text-slate-500 mt-3 max-w-3xl leading-relaxed">
            Gaps in the year series are archival, not historical: the register is missing for
            1941–43 and 1945, and the press has the hospital working throughout. 1932's level is
            itself a reading decision — see the QUOTE_NONE note in the generator.
          </p>

          <h3 className="text-sm font-semibold text-slate-700 mt-8 mb-3">
            The last months, in counts
          </h3>
          <div className="overflow-x-auto">
            <table className="text-xs border-collapse">
              <thead><tr><TH>Month</TH>{MCJ.map(m => <TH key={m} right>{m}</TH>)}<TH right>Total</TH></tr></thead>
              <tbody>
                {withdrawal.lateMonths.map(m => (
                  <tr key={m.month}>
                    <TD>{m.month}</TD>
                    {MCJ.map(k => (
                      <TD key={k} right>
                        <span className={k === 'Jewish' && m.month.startsWith('1948')
                          ? 'font-semibold text-slate-900' : ''}>{m[k]}</span>
                      </TD>
                    ))}
                    <TD right>{m.n}</TD>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-slate-500 mt-3 max-w-3xl leading-relaxed">
            One Jewish admission in January 1948, two in February, none thereafter — the register's
            side of the removal of Jewish patients that the Mitteilungsblatt reports for that month.
          </p>
        </Section>

        {/* ---------------------------------------------------------- 06 */}
        <Section
          n="06"
          title="Who treated whom"
          lede={
            <p>
              The register was not built to record the staff, but it records them when they fell
              ill: {staff.n} admissions carry a nursing or medical title, {staff.female} of them
              women, and {staff.inBritishSection} were admitted to the British Section. Their
              confessional profile inverts the patient body's — a majority-Muslim population of
              patients, cared for by a nursing corps that was disproportionately Jewish and
              Christian. Read it against the named establishment in MidEastMed, which is
              overwhelmingly Arab and Armenian doctors, pharmacists and midwives under British
              senior officers: the shared space was a workplace before it was a ward.
            </p>
          }
        >
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <div className="grid grid-cols-[7rem_1fr_1fr] gap-4 text-xs font-semibold
                            text-slate-500 pb-2 border-b border-slate-200 mb-2">
              <div />
              <div>Share of staff admissions</div>
              <div>Share of all admissions</div>
            </div>
            {staff.comparison.map(c => (
              <div key={c.religion} className="grid grid-cols-[7rem_1fr_1fr] gap-4 items-center py-1.5">
                <div className="text-sm text-slate-700 text-right">{c.religion}</div>
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-5 bg-slate-100 rounded-sm overflow-hidden">
                    <div className="h-full rounded-sm"
                         style={{ width: `${c.staffPct}%`, background: REL[c.religion as keyof typeof REL] }} />
                  </div>
                  <span className="text-xs text-slate-500 tabular-nums w-14 shrink-0">
                    {c.staffPct}% <span className="text-slate-300">({c.staffN})</span>
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-5 bg-slate-100 rounded-sm overflow-hidden">
                    <div className="h-full rounded-sm opacity-40"
                         style={{ width: `${c.allPct}%`, background: REL[c.religion as keyof typeof REL] }} />
                  </div>
                  <span className="text-xs text-slate-500 tabular-nums w-10 shrink-0">{c.allPct}%</span>
                </div>
              </div>
            ))}
          </div>
          <Caveat>
            Occupation is recorded for a minority of admissions, and a hospital worker who never
            fell ill never appears. This is a sample of the staff produced by illness, not a staff
            list — it establishes that the corps was mixed and skewed away from the patient body,
            not the size of the skew.
          </Caveat>
          <TableView label="Titles as written">
            <table className="w-full text-xs border-collapse">
              <thead><tr><TH>Occupation</TH><TH right>n</TH></tr></thead>
              <tbody>
                {staff.occupations.map(o => (
                  <tr key={o.name}><TD>{o.name}</TD><TD right>{o.n}</TD></tr>
                ))}
              </tbody>
            </table>
          </TableView>
        </Section>

        {/* ---------------------------------------------------------- 07 */}
        <Section
          n="07"
          title="Free treatment, and who paid"
          lede={
            <p>
              The payment column had to be read before it could be counted. It is a{' '}
              <strong>gratis marker</strong>, not a completeness field: the clerk wrote{' '}
              <em>Gratis</em> when treatment was free and left the cell empty when a fee was
              charged, entering the fee in the Rate column instead. So a blank is evidence of
              payment, and the hospital treated{' '}
              <Num v={100 * payment.evidence.split.gratis / data.meta.records} suffix="%" /> of its
              admissions free. The interesting part is who the exceptions were — and once class is
              held constant, they are barely the groups at all.
            </p>
          }
        >
          <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6">
            <h3 className="text-sm font-semibold text-slate-700 mb-3">
              Why the blank is a charge and not a silence
            </h3>
            <div className="grid sm:grid-cols-3 gap-x-6 gap-y-3 text-xs text-slate-600">
              <div>
                <div className="font-semibold text-slate-700 mb-1">The Rate column is complementary</div>
                Rate is filled for <strong><Num v={payment.evidence.blankWithRatePct} suffix="%" /></strong>{' '}
                of blank rows against <strong><Num v={payment.evidence.gratisWithRatePct} suffix="%" /></strong>{' '}
                of <em>Gratis</em> rows. The blanks carry money.
              </div>
              <div>
                <div className="font-semibold text-slate-700 mb-1">It tracks class like a fee</div>
                Blank for{' '}
                {(['1', '2', '3'] as const).map((k, i) => (
                  <span key={k}>
                    {i > 0 && ', '}
                    <strong><Num v={payment.evidence.blankByClass[k]} suffix="%" /></strong> of class {k}
                  </span>
                ))}. The paying classes are the blank ones.
              </div>
              <div>
                <div className="font-semibold text-slate-700 mb-1">It is not a skipped column</div>
                <strong><Num v={payment.evidence.pages.mixedPct} suffix="%" /></strong> of pages mix
                blank with filled rows and only{' '}
                <Num v={payment.evidence.pages.allBlankPct} suffix="%" /> are wholly blank — it
                varies patient by patient, on one page.
              </div>
            </div>
            <div className="flex h-7 gap-[2px] mt-5" role="img"
                 aria-label="Marked gratis, charged with a recorded rate, and genuinely unknown">
              {[
                { k: 'Marked gratis', v: payment.evidence.split.gratis, c: NEUTRAL },
                { k: 'Charged, rate recorded', v: payment.evidence.split.chargedWithRate, c: SERIES[3] },
                { k: 'Blank, no rate — unknown', v: payment.evidence.split.unknown, c: RESIDUE }
              ].map((seg, i, arr) => {
                const total = arr.reduce((a, b) => a + b.v, 0);
                return (
                  <div key={seg.k} className="flex items-center justify-center overflow-hidden
                                              first:rounded-l last:rounded-r"
                       style={{ width: `${(seg.v / total) * 100}%`, background: seg.c }}
                       title={`${seg.k}: ${seg.v.toLocaleString()}`}>
                    <span className={`text-[11px] font-medium tabular-nums px-1
                                      ${i === 2 ? 'text-slate-600' : 'text-white'}`}>
                      {Math.round((seg.v / total) * 100)}%
                    </span>
                  </div>
                );
              })}
            </div>
            <ul className="flex flex-wrap gap-x-5 gap-y-1 mt-2">
              {[
                { label: `Marked gratis (${payment.evidence.split.gratis.toLocaleString()})`, color: NEUTRAL },
                { label: `Charged, rate recorded (${payment.evidence.split.chargedWithRate.toLocaleString()})`, color: SERIES[3] },
                { label: `Blank, no rate — unknown (${payment.evidence.split.unknown.toLocaleString()})`, color: RESIDUE }
              ].map(i => (
                <li key={i.label} className="flex items-center gap-1.5 text-[11px] text-slate-500">
                  <span className="w-2.5 h-2.5 rounded-sm shrink-0" style={{ background: i.color }} />
                  {i.label}
                </li>
              ))}
            </ul>
          </div>

          <h3 className="text-sm font-semibold text-slate-700 mb-1">
            Treated free, by group — and within class
          </h3>
          <p className="text-xs text-slate-500 mb-4 max-w-3xl">
            The headline spread is large and almost entirely a class effect. Within third class the
            three are within 9 points, and the order changes: Jewish patients are the <em>most</em>{' '}
            likely to be treated free. The median fee where one was charged says the same thing from
            the other side.
          </p>
          <div className="bg-white rounded-xl border border-slate-200 p-5 mb-5">
            <div className="grid grid-cols-[7rem_1fr_1fr] gap-4 text-xs font-semibold
                            text-slate-500 pb-2 border-b border-slate-200 mb-2">
              <div />
              <div>All admissions</div>
              <div>Third class only</div>
            </div>
            {payment.byGroup.map(r => (
              <div key={r.group} className="grid grid-cols-[7rem_1fr_1fr] gap-4 items-center py-1.5">
                <div className="text-sm text-slate-700 text-right">{r.group}</div>
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-5 bg-slate-100 rounded-sm overflow-hidden">
                    <div className="h-full rounded-sm"
                         style={{ width: `${r.gratisPct}%`, background: REL[r.group as keyof typeof REL] }} />
                  </div>
                  <span className="text-xs text-slate-500 tabular-nums w-10 shrink-0">
                    {r.gratisPct}%
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-5 bg-slate-100 rounded-sm overflow-hidden">
                    <div className="h-full rounded-sm"
                         style={{ width: `${r.gratisThirdClassPct}%`,
                                  background: REL[r.group as keyof typeof REL] }} />
                  </div>
                  <span className="text-xs text-slate-500 tabular-nums w-10 shrink-0">
                    {r.gratisThirdClassPct}%
                  </span>
                </div>
              </div>
            ))}
            <p className="text-[11px] text-slate-400 mt-3 leading-relaxed">
              Median fee where a rate was recorded:{' '}
              {payment.byGroup.map((r, i) => (
                <span key={r.group}>
                  {i > 0 && ' · '}{r.group} <strong>{r.medianRate ?? '—'} mils</strong>
                  <span className="text-slate-300"> (n={r.rateN.toLocaleString()})</span>
                </span>
              ))}. The Christian median is nearly three times the Muslim one and five times the
              Jewish — which is the British officials inside that category again, not a fee scale
              that varied by religion.
            </p>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h3 className="text-sm font-semibold text-slate-700 mb-3">
              Treated free, by class
            </h3>
            <table className="text-xs border-collapse">
              <thead><tr><TH>Class</TH>{MCJ.map(m => <TH key={m} right>{m}</TH>)}</tr></thead>
              <tbody>
                {payment.byClass.map(r => (
                  <tr key={String(r.class)}>
                    <TD>Class {String(r.class)}</TD>
                    {MCJ.map(m => (
                      <TD key={m} right>
                        {r[m] === null || r[m] === undefined
                          ? <span className="text-slate-300">—</span>
                          : `${Number(r[m]).toFixed(1)}%`}
                      </TD>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-[11px] text-slate-400 mt-3 leading-relaxed">
              First class paid, third class largely did not, and that — not confession — is what the
              column measures.
            </p>
          </div>
          <TableView label="With nationality crossed in">
            <table className="w-full text-xs border-collapse">
              <thead><tr><TH>Group</TH><TH right>n</TH><TH right>Gratis</TH>
                <TH right>Gratis, 3rd class</TH></tr></thead>
              <tbody>
                {payment.byMixed.map(r => (
                  <tr key={r.group}>
                    <TD>{r.group}</TD><TD right>{r.n.toLocaleString()}</TD>
                    <TD right><Num v={r.gratisPct} suffix="%" /></TD>
                    <TD right><Num v={r.gratisThirdClassPct} suffix="%" />
                      <span className="text-slate-400"> (n={r.thirdClassN.toLocaleString()})</span></TD>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableView>
        </Section>

        {/* ---------------------------------------------------------- 08 */}
        <Section
          n="08"
          title="What the register does not say"
          lede={
            <p>
              The diagnostic gaps are temporal, not confessional: coverage collapses as the Mandate
              ends, in the same years for everyone, so a comparison between groups is not being
              quietly distorted by who got recorded. The one exception is the ward column, which
              fails unevenly by group in the late years — and that is the caution to carry into the
              article.
            </p>
          }
        >
          <div className="bg-white rounded-xl border border-slate-200 p-5 max-w-2xl">
            <h3 className="text-sm font-semibold text-slate-700 mb-3">Column coverage</h3>
            {gaps.coverage.map(c => (
              <div key={c.column} className="grid grid-cols-[11rem_1fr_3rem] gap-3 items-center py-0.5">
                <div className="text-[11px] text-slate-600 text-right truncate" title={c.column}>
                  {c.column}
                </div>
                <div className="h-4 bg-slate-100 rounded-sm overflow-hidden">
                  <div className="h-full rounded-sm"
                       style={{ width: `${c.pct}%`,
                                background: c.pct < 50 ? SERIES[7] : c.pct < 90 ? SERIES[3] : NEUTRAL }} />
                </div>
                <div className="text-[11px] text-slate-500 tabular-nums">{c.pct}%</div>
              </div>
            ))}
            <p className="text-[11px] text-slate-400 mt-3 leading-relaxed">
              Procedure at 1.8% is not a gap to be filled — the register simply did not record
              operations as a rule.
            </p>
          </div>

          <h3 className="text-sm font-semibold text-slate-700 mt-8 mb-1">
            Missingness is a date, not a religion
          </h3>
          <p className="text-xs text-slate-500 mb-4 max-w-3xl">
            ICD-9, ward and result coverage by year. All three fail together as the Mandate ends —
            a register recording less, not a dataset with a hole in it.
          </p>
          <div className="bg-white rounded-xl border border-slate-200 p-5 overflow-x-auto">
            <table className="text-xs border-collapse min-w-full">
              <thead><tr><TH>Year</TH><TH right>n</TH><TH right>ICD-9 missing</TH>
                <TH right>Ward missing</TH><TH right>Result missing</TH></tr></thead>
              <tbody>
                {gaps.byYear.map(y => (
                  <tr key={y.year}>
                    <TD>{y.year}</TD><TD right>{y.n.toLocaleString()}</TD>
                    <TD right><Num v={y.icd9Missing} suffix="%" /></TD>
                    <TD right><Num v={y.wardMissing} suffix="%" /></TD>
                    <TD right><Num v={y.resultMissing} suffix="%" /></TD>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h3 className="text-sm font-semibold text-slate-700 mt-8 mb-1">
            The exception: ward, in the late years
          </h3>
          <p className="text-xs text-slate-500 mb-4 max-w-3xl">
            Here the failure is not even-handed. By 1947 the ward is missing for over half of Jewish
            admissions and a third of Muslim ones, so late-period ward shares should not be read as
            a comparison between groups.
          </p>
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <table className="text-xs border-collapse">
              <thead><tr><TH>Year</TH>{MCJ.map(m => <TH key={m} right>{m}</TH>)}</tr></thead>
              <tbody>
                {gaps.wardMissingLate.map(r => (
                  <tr key={String(r.year)}>
                    <TD>{String(r.year)}</TD>
                    {MCJ.map(m => (
                      <TD key={m} right>
                        {r[m] === null || r[m] === undefined
                          ? <span className="text-slate-300">—</span>
                          : <span className={Number(r[m]) > 50 ? 'font-semibold text-amber-700' : ''}>
                              {Number(r[m]).toFixed(1)}%
                            </span>}
                      </TD>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-[11px] text-slate-400 mt-3 leading-relaxed">
              Ward-missing admissions also die slightly more often than ward-known ones
              (<Num v={gaps.wardBias.missing.cfr} suffix="%" dp={2} /> against{' '}
              <Num v={gaps.wardBias.known.cfr} suffix="%" dp={2} />), so the blanks are not a random
              sample of the register either.
            </p>
          </div>
        </Section>

        <footer className="border-t border-slate-200 pt-6 mt-4 text-xs text-slate-500
                           leading-relaxed max-w-3xl">
          <p className="mb-2">
            <strong className="text-slate-600">Sources.</strong> The register figures are computed
            by <code className="bg-white px-1 py-0.5 rounded border border-slate-200">pipeline/shared_space_figures.py</code>{' '}
            over {data.meta.records.toLocaleString()} admissions. The building's plan is the 1936
            Schedule of Accommodation and the 1935 memorandum in Israel State Archives file
            0005xx0; the named establishment is MidEastMed (ERC), institution 60387, CC-BY 4.0.
          </p>
          <p>{data.meta.note}</p>
        </footer>
        </div>
      </div>

      <HelpPanel title="How to read this" sections={HELP} storageKey="help.shared-space" />
    </div>
  );
};

export default SharedSpaceView;
