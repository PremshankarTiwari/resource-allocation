import { useMemo } from "react";
import type { AlgorithmInfo, Job, Scenario, Solution } from "../types";
import { PRIORITY_COLOR, PRIORITY_LABEL, fmtTime, skillLabel } from "../format";

interface Props {
  algos: AlgorithmInfo[];
  scenario: Scenario;
  solutions: Record<string, Solution>;
  selectedJob: string | null;
  onSelectJob: (id: string | null) => void;
}

export default function JobInspector({ algos, scenario, solutions, selectedJob, onSelectJob }: Props) {
  const shown = algos.filter((a) => solutions[a.key]);
  const techName = useMemo(() => new Map(scenario.technicians.map((t) => [t.id, t.name])), [scenario]);

  const owner = useMemo(() => {
    const out: Record<string, Map<string, string>> = {};
    for (const a of shown) out[a.key] = new Map(solutions[a.key].assignments.map((x) => [x.job_id, x.technician_id]));
    return out;
  }, [shown, solutions]);

  // Jobs where the algorithms made different decisions: the interesting ones to inspect.
  // Coverage differences (served by some plans, not others) matter most, so they come first.
  const { coverage, reassigned } = useMemo(() => {
    const coverage: Job[] = [];
    const reassigned: Job[] = [];
    for (const j of scenario.jobs) {
      const owners = shown.map((a) => owner[a.key]?.get(j.id) ?? null);
      if (new Set(owners).size <= 1) continue;
      (owners.includes(null) ? coverage : reassigned).push(j);
    }
    return { coverage, reassigned };
  }, [scenario, shown, owner]);
  const differing = coverage.length + reassigned.length;

  const chipList = (jobs: Job[]) => (
    <div className="chips" role="list">
      {jobs.map((j) => (
        <button
          key={j.id}
          role="listitem"
          className={`chip${j.id === selectedJob ? " on" : ""}`}
          style={{ borderLeftColor: PRIORITY_COLOR[j.priority] }}
          onClick={() => onSelectJob(j.id === selectedJob ? null : j.id)}
        >
          {j.id}
        </button>
      ))}
    </div>
  );

  const job = scenario.jobs.find((j) => j.id === selectedJob);

  return (
    <section className="card inspector">
      <h3>Where the plans differ</h3>
      {shown.length < 2 ? (
        <p className="note">Run at least two algorithms to compare decisions.</p>
      ) : differing === 0 ? (
        <p className="note">Every algorithm made the same assignments for this scenario.</p>
      ) : (
        <>
          <p className="note">
            {differing} of {scenario.jobs.length} jobs were handled differently. Pick one to see each decision.
          </p>
          {coverage.length > 0 && (
            <>
              <h4 className="group">Served by some plans but not others ({coverage.length})</h4>
              {chipList(coverage)}
            </>
          )}
          {reassigned.length > 0 && (
            <>
              <h4 className="group">Served by every plan, by different technicians ({reassigned.length})</h4>
              {chipList(reassigned)}
            </>
          )}
        </>
      )}

      {job ? (
        <div className="job">
          <div className="job-head">
            <h4>
              {job.id} <span className="site">{job.site}</span>
            </h4>
            <button className="link" onClick={() => onSelectJob(null)}>Clear selection</button>
          </div>
          <p className="facts">
            <span className="pri" style={{ color: PRIORITY_COLOR[job.priority] }}>{PRIORITY_LABEL[job.priority]}</span>
            {" | "}needs {job.required_skills.map(skillLabel).join(" + ")}
            {" | "}start between {fmtTime(job.window_start)} and {fmtTime(job.window_end)}
            {" | "}{job.duration} min on site
          </p>
          <ul className="decisions">
            {shown.map((a) => {
              const e = solutions[a.key].explanations.find((x) => x.job_id === job.id);
              const who = e?.assigned_to;
              return (
                <li key={a.key}>
                  <span className="algo">{a.name}</span>
                  <span className={`who${who ? "" : " none"}`}>
                    {who ? `${techName.get(who)} (${who})` : "Not assigned"}
                  </span>
                  <p>{e?.summary}</p>
                </li>
              );
            })}
          </ul>
        </div>
      ) : (
        <p className="note empty">Click any job on a map, or a job above, to compare how each algorithm handled it.</p>
      )}
    </section>
  );
}
