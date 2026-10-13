import type { AlgorithmInfo, Metrics, Solution } from "../types";

type Row = {
  key: keyof Metrics;
  label: string;
  hint: string;
  better: "higher" | "lower" | null;
  fmt: (v: number) => string;
};

const pct = (v: number) => `${v.toFixed(1)}%`;

export const ROWS: Row[] = [
  { key: "coverage_pct", label: "Jobs covered", hint: "Share of jobs assigned", better: "higher", fmt: pct },
  { key: "critical_coverage_pct", label: "Critical jobs covered", hint: "Share of critical jobs assigned", better: "higher", fmt: pct },
  { key: "priority_weighted_coverage_pct", label: "Priority-weighted coverage", hint: "Coverage weighted by each job's priority reward", better: "higher", fmt: pct },
  { key: "total_travel_km", label: "Total driving", hint: "Kilometres including the drive home", better: "lower", fmt: (v) => `${v.toFixed(0)} km` },
  { key: "travel_km_per_job", label: "Driving per job", hint: "Total driving / jobs covered", better: "lower", fmt: (v) => `${v.toFixed(1)} km` },
  { key: "avg_wait_min", label: "Average wait on site", hint: "Minutes waiting for a time window to open", better: "lower", fmt: (v) => `${v.toFixed(0)} min` },
  { key: "utilization_pct", label: "Utilization", hint: "Work + driving time / total shift time", better: null, fmt: pct },
  { key: "workload_std", label: "Workload spread", hint: "Std. deviation of jobs per technician; lower is fairer", better: "lower", fmt: (v) => v.toFixed(2) },
  { key: "objective", label: "Total cost", hint: "Route cost + reward lost on unserved jobs; the number every algorithm tries to minimize", better: "lower", fmt: (v) => Math.round(v).toLocaleString() },
  { key: "runtime_ms", label: "Runtime", hint: "Server-side solve time", better: "lower", fmt: (v) => `${v.toFixed(1)} ms` },
];

export function bestKeys(row: Row, algos: AlgorithmInfo[], solutions: Record<string, Solution>): Set<string> {
  if (!row.better) return new Set();
  const vals = algos.filter((a) => solutions[a.key]).map((a) => [a.key, solutions[a.key].metrics[row.key]] as const);
  if (vals.length < 2) return new Set();
  const target = row.better === "higher" ? Math.max(...vals.map((v) => v[1])) : Math.min(...vals.map((v) => v[1]));
  const winners = vals.filter((v) => Math.abs(v[1] - target) < 1e-9).map((v) => v[0]);
  return winners.length === vals.length ? new Set() : new Set(winners);
}

export default function MetricsTable({ algos, solutions }: { algos: AlgorithmInfo[]; solutions: Record<string, Solution> }) {
  const shown = algos.filter((a) => solutions[a.key]);
  return (
    <section className="card metrics">
      <h3>Metrics</h3>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">Metric</th>
              {shown.map((a) => <th scope="col" key={a.key}>{a.name}</th>)}
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => {
              const best = bestKeys(row, shown, solutions);
              return (
                <tr key={row.key}>
                  <th scope="row">
                    {row.label}
                    <span className="hint">{row.hint}</span>
                  </th>
                  {shown.map((a) => (
                    <td key={a.key} className={best.has(a.key) ? "best" : ""}>
                      {row.fmt(solutions[a.key].metrics[row.key])}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="note">Highlighted cells are the best value in that row. Ties are not highlighted.</p>
    </section>
  );
}
