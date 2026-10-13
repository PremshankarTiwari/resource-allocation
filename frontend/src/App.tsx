import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api";
import type { AlgorithmInfo, Job, Location, Priority, Scenario, Solution, Weights } from "./types";
import MapPanel, { type MapSync } from "./components/MapPanel";
import MetricsTable, { ROWS, bestKeys } from "./components/MetricsTable";
import JobInspector from "./components/JobInspector";
import { PRIORITY_COLOR, PRIORITY_LABEL, skillLabel } from "./format";

const DEFAULT_WEIGHTS: Weights = {
  travel_km: 1, idle_minute: 0.2, overqualified_skill: 3,
  reward_normal: 150, reward_high: 400, reward_critical: 1000,
};
const SKILLS = ["mechanical", "electrical", "hydraulics", "controls", "high_voltage"];

const WEIGHT_FIELDS: { key: keyof Weights; label: string; step: number }[] = [
  { key: "travel_km", label: "Cost per km driven", step: 0.1 },
  { key: "idle_minute", label: "Cost per minute waiting", step: 0.1 },
  { key: "overqualified_skill", label: "Cost per unused specialist skill", step: 0.5 },
  { key: "reward_critical", label: "Value of serving a critical job", step: 50 },
  { key: "reward_high", label: "Value of serving a high job", step: 50 },
  { key: "reward_normal", label: "Value of serving a normal job", step: 10 },
];

export default function App() {
  const [algos, setAlgos] = useState<AlgorithmInfo[]>([]);
  const [enabled, setEnabled] = useState<string[]>([]);
  const [params, setParams] = useState({ seed: 7, technicians: 12, jobs: 48, max_jobs: 5 });
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [weights, setWeights] = useState<Weights>(DEFAULT_WEIGHTS);
  const [solutions, setSolutions] = useState<Record<string, Solution>>({});
  const [selectedJob, setSelectedJob] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [planning, setPlanning] = useState(false);
  const [addMode, setAddMode] = useState(false);
  const [newJob, setNewJob] = useState<{ priority: Priority; skill: string }>({ priority: 3, skill: "electrical" });

  const sync = useRef<MapSync>({ maps: new Set(), busy: false }).current;
  const requestId = useRef(0);

  const loadScenario = useCallback(async (p = params) => {
    try {
      setError(null);
      setSelectedJob(null);
      setScenario(await api.scenario(p));
    } catch (e) {
      setError((e as Error).message);
    }
  }, [params]);

  useEffect(() => {
    api.algorithms()
      .then((a) => {
        console.log(a);
        setAlgos(a);
        setEnabled(a.map((x) => x.key)); 
      })
      .catch((e) => setError(e.message));
    loadScenario();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Re-plan whenever the scenario, algorithm selection or weights change (debounced).
  useEffect(() => {
    if (!scenario || enabled.length === 0) return;
    const id = ++requestId.current;
    const timer = setTimeout(async () => {
      setPlanning(true);
      try {
        const res = await api.solve(scenario, enabled, weights);
        console.log(res);
        if (id === requestId.current) { setSolutions(res.solutions); setError(null); }
      } catch (e) {
        if (id === requestId.current) setError((e as Error).message);
      } finally {
        if (id === requestId.current) setPlanning(false);
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [scenario, enabled, weights]);

  const addJob = useCallback((loc: Location) => {
    setScenario((s) => {
      if (!s) return s;
      const next = Math.max(0, ...s.jobs.map((j) => parseInt(j.id.slice(1), 10) || 0)) + 1;
      const job: Job = {
        id: `J${String(next).padStart(3, "0")}`,
        site: "Added on map",
        location: loc,
        required_skills: [newJob.skill],
        window_start: 480,
        window_end: 900,
        duration: 60,
        priority: newJob.priority,
      };
      setSelectedJob(job.id);
      return { ...s, jobs: [...s.jobs, job] };
    });
  }, [newJob]);

  const shownAlgos = algos.filter((a) => enabled.includes(a.key));
  const stripBest = useMemo(() => {
    const pick = (k: string) => bestKeys(ROWS.find((r) => r.key === k)!, shownAlgos, solutions);
    return { coverage: pick("coverage_pct"), objective: pick("objective"), travel: pick("total_travel_km") };
  }, [shownAlgos, solutions]);

  const toggleAlgo = (key: string) =>
    setEnabled((cur) => (cur.includes(key) ? cur.filter((k) => k !== key) : algos.map((a) => a.key).filter((k) => k === key || cur.includes(k))));

  return (
    <div className="app">
      <header className="top">
        <div className="title">
          <h1>Dispatch planner</h1>
          <p>Three ways to assign field technicians to a day of maintenance jobs, compared on the same map.</p>
        </div>
        <span className={`status${planning ? " busy" : ""}`} aria-live="polite">
          {planning ? "Planning..." : scenario ? `${scenario.technicians.length} technicians, ${scenario.jobs.length} jobs` : ""}
        </span>
      </header>

      <form
        className="controls"
        onSubmit={(e) => { e.preventDefault(); loadScenario(); }}
        aria-label="Scenario and planning settings"
      >
        <fieldset>
          <legend>Scenario</legend>
          {([
            ["seed", "Seed", 0, 9999],
            ["technicians", "Technicians", 1, 60],
            ["jobs", "Jobs", 1, 300],
            ["max_jobs", "Jobs per technician", 1, 12],
          ] as const).map(([k, label, min, max]) => (
            <label key={k}>
              {label}
              <input
                type="number" min={min} max={max} value={params[k]}
                onChange={(e) => setParams({ ...params, [k]: Math.max(min, Math.min(max, Number(e.target.value) || min)) })}
              />
            </label>
          ))}
          <button type="submit" className="primary">Generate scenario</button>
        </fieldset>

        <fieldset>
          <legend>Algorithms</legend>
          {algos.map((a) => (
            <label key={a.key} className="check">
              <input type="checkbox" checked={enabled.includes(a.key)} onChange={() => toggleAlgo(a.key)} />
              {a.name}
            </label>
          ))}
        </fieldset>

        <fieldset>
          <legend>Add a job</legend>
          <label>
            Priority
            <select value={newJob.priority} onChange={(e) => setNewJob({ ...newJob, priority: Number(e.target.value) as Priority })}>
              {([3, 2, 1] as Priority[]).map((p) => <option key={p} value={p}>{PRIORITY_LABEL[p]}</option>)}
            </select>
          </label>
          <label>
            Skill needed
            <select value={newJob.skill} onChange={(e) => setNewJob({ ...newJob, skill: e.target.value })}>
              {SKILLS.map((s) => <option key={s} value={s}>{skillLabel(s)}</option>)}
            </select>
          </label>
          <button type="button" className={addMode ? "primary on" : ""} aria-pressed={addMode} onClick={() => setAddMode(!addMode)}>
            {addMode ? "Click a map to place it" : "Place job on map"}
          </button>
        </fieldset>

        <details className="weights">
          <summary>Cost weights</summary>
          <div className="weight-grid">
            {WEIGHT_FIELDS.map((f) => (
              <label key={f.key}>
                {f.label}
                <input
                  type="number" min={0} step={f.step} value={weights[f.key]}
                  onChange={(e) => setWeights({ ...weights, [f.key]: Math.max(0, Number(e.target.value) || 0) })}
                />
              </label>
            ))}
            <button type="button" onClick={() => setWeights(DEFAULT_WEIGHTS)}>Reset weights</button>
          </div>
        </details>
      </form>

      {error && <div className="error" role="alert">{error}</div>}

      <div className="legend" aria-label="Map legend">
        {([3, 2, 1] as Priority[]).map((p) => (
          <span key={p}><i className="dot" style={{ background: PRIORITY_COLOR[p] }} />{PRIORITY_LABEL[p]} job</span>
        ))}
        <span><i className="dot hollow" />Unassigned</span>
        <span><i className="sq" />Technician home</span>
        <span><i className="ring" />Selected job</span>
        <span className="tip">Pan or zoom any map: the others follow.</span>
      </div>

      {scenario && (
        <div className={`maps n${shownAlgos.length}`}>
          {shownAlgos.map((a) => (
            <MapPanel
              key={a.key}
              info={a}
              scenario={scenario}
              solution={solutions[a.key]}
              sync={sync}
              selectedJob={selectedJob}
              onSelectJob={setSelectedJob}
              addMode={addMode}
              onAddJob={addJob}
              isBest={(m) => stripBest[m].has(a.key)}
            />
          ))}
        </div>
      )}
      {shownAlgos.length === 0 && <p className="empty-state">Turn on at least one algorithm to see a plan.</p>}

      {scenario && shownAlgos.length > 0 && (
        <div className="lower">
          <MetricsTable algos={shownAlgos} solutions={solutions} />
          <JobInspector
            algos={shownAlgos}
            scenario={scenario}
            solutions={solutions}
            selectedJob={selectedJob}
            onSelectJob={setSelectedJob}
          />
        </div>
      )}
    </div>
  );
}
