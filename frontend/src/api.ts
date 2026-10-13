import type { AlgorithmInfo, Scenario, Solution, Weights } from "./types";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch {
    throw new Error("Can't reach the backend. Start it with `uvicorn app.main:app --reload` in the backend folder.");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = typeof body?.detail === "string" ? body.detail : JSON.stringify(body?.detail ?? res.statusText);
    throw new Error(`Request failed (${res.status}): ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  algorithms: () => request<AlgorithmInfo[]>("/api/algorithms"),
  scenario: (p: { seed: number; technicians: number; jobs: number; max_jobs: number }) =>
    request<Scenario>(`/api/scenario?${new URLSearchParams(Object.entries(p).map(([k, v]) => [k, String(v)]))}`),
  solve: (scenario: Scenario, algorithms: string[], weights: Weights) =>
    request<{ solutions: Record<string, Solution> }>("/api/solve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenario, algorithms, weights }),
    }),
};
