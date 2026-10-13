import { useEffect, useMemo } from "react";
import L from "leaflet";
import { CircleMarker, MapContainer, Marker, Polyline, TileLayer, Tooltip, useMap, useMapEvents } from "react-leaflet";
import type { AlgorithmInfo, Location, Scenario, Solution } from "../types";
import { PRIORITY_COLOR, PRIORITY_LABEL, fmtTime, techColor } from "../format";

export interface MapSync {
  maps: Set<L.Map>;
  busy: boolean;
}

interface Props {
  info: AlgorithmInfo;
  scenario: Scenario;
  solution?: Solution;
  sync: MapSync;
  selectedJob: string | null;
  onSelectJob: (id: string | null) => void;
  addMode: boolean;
  onAddJob: (loc: Location) => void;
  isBest: (metric: "coverage" | "objective" | "travel") => boolean;
}

/** Keeps every comparison map on the same view, so differences line up. */
function SyncView({ sync }: { sync: MapSync }) {
  const map = useMap();
  useEffect(() => {
    sync.maps.add(map);
    const follow = () => {
      if (sync.busy) return;
      sync.busy = true;
      for (const other of sync.maps) {
        if (other !== map) other.setView(map.getCenter(), map.getZoom(), { animate: false });
      }
      sync.busy = false;
    };
    map.on("move", follow);
    map.on("zoomend", follow);
    return () => {
      map.off("move", follow);
      map.off("zoomend", follow);
      sync.maps.delete(map);
    };
  }, [map, sync]);
  return null;
}

function FitToScenario({ scenario }: { scenario: Scenario }) {
  const map = useMap();
  const key = scenario.technicians.length + ":" + scenario.jobs.length + ":" + (scenario.jobs[0]?.id ?? "");
  useEffect(() => {
    const pts: [number, number][] = [
      ...scenario.technicians.map((t) => [t.home.lat, t.home.lon] as [number, number]),
      ...scenario.jobs.map((j) => [j.location.lat, j.location.lon] as [number, number]),
    ];
    if (pts.length) map.fitBounds(L.latLngBounds(pts), { padding: [18, 18], animate: false });
    // Re-fit only when a new scenario is generated, not when a job is added.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return null;
}

function ClickToAdd({ active, onAdd }: { active: boolean; onAdd: (loc: Location) => void }) {
  useMapEvents({
    click(e) {
      if (active) onAdd({ lat: +e.latlng.lat.toFixed(5), lon: +e.latlng.lng.toFixed(5) });
    },
  });
  return null;
}

const homeIcon = (color: string, label: string) =>
  L.divIcon({
    className: "home-icon",
    html: `<span style="background:${color}">${label}</span>`,
    iconSize: [22, 16],
    iconAnchor: [11, 8],
  });

export default function MapPanel(p: Props) {
  const { scenario, solution, selectedJob } = p;
  const techIndex = useMemo(() => new Map(scenario.technicians.map((t, i) => [t.id, i])), [scenario]);
  const jobById = useMemo(() => new Map(scenario.jobs.map((j) => [j.id, j])), [scenario]);
  const assignedTo = useMemo(
    () => new Map(solution?.assignments.map((a) => [a.job_id, a.technician_id]) ?? []),
    [solution],
  );
  const selectedTech = selectedJob ? assignedTo.get(selectedJob) ?? null : null;
  const m = solution?.metrics;

  return (
    <section className="panel" aria-label={`${p.info.name} plan`}>
      <header className="panel-head">
        <h2>{p.info.name}</h2>
        <p>{p.info.description}</p>
      </header>

      <div className={`map-wrap${p.addMode ? " adding" : ""}`}>
        <MapContainer center={[30.27, -97.74]} zoom={9} scrollWheelZoom className="map">
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <SyncView sync={p.sync} />
          <FitToScenario scenario={scenario} />
          <ClickToAdd active={p.addMode} onAdd={p.onAddJob} />

          {solution?.routes.map((r) => {
            if (!r.stops.length) return null;
            const t = scenario.technicians[techIndex.get(r.technician_id)!];
            const path: [number, number][] = [
              [t.home.lat, t.home.lon],
              ...r.stops.map((s) => {
                const j = jobById.get(s.job_id)!;
                return [j.location.lat, j.location.lon] as [number, number];
              }),
              [t.home.lat, t.home.lon],
            ];
            const dim = selectedTech !== null && selectedTech !== r.technician_id;
            const focus = selectedTech === r.technician_id;
            return (
              <Polyline
                key={r.technician_id}
                positions={path}
                pathOptions={{
                  color: techColor(techIndex.get(r.technician_id)!),
                  weight: focus ? 5 : 2.5,
                  opacity: dim ? 0.15 : 0.85,
                }}
              />
            );
          })}

          {scenario.technicians.map((t, i) => (
            <Marker key={t.id} position={[t.home.lat, t.home.lon]} icon={homeIcon(techColor(i), t.id.replace("T", ""))}>
              <Tooltip>
                <strong>{t.name}</strong> ({t.id})<br />
                {t.skills.join(", ")}<br />
                Shift {fmtTime(t.shift_start)}-{fmtTime(t.shift_end)}
              </Tooltip>
            </Marker>
          ))}

          {scenario.jobs.map((j) => {
            const assigned = assignedTo.has(j.id);
            const color = PRIORITY_COLOR[j.priority];
            return (
              <CircleMarker
                key={j.id}
                center={[j.location.lat, j.location.lon]}
                radius={j.priority === 3 ? 7 : 5.5}
                pathOptions={{
                  color,
                  weight: assigned ? 1.5 : 2,
                  fillColor: assigned ? color : "#ffffff",
                  fillOpacity: assigned ? 0.95 : 1,
                  dashArray: assigned ? undefined : "2 2",
                }}
                eventHandlers={{ click: () => p.onSelectJob(j.id === selectedJob ? null : j.id) }}
              >
                <Tooltip>
                  <strong>{j.id}</strong> {PRIORITY_LABEL[j.priority]}<br />
                  {j.site}<br />
                  {assigned ? `Assigned to ${assignedTo.get(j.id)}` : "Unassigned"}
                </Tooltip>
              </CircleMarker>
            );
          })}

          {selectedJob && jobById.get(selectedJob) && (
            <CircleMarker
              center={[jobById.get(selectedJob)!.location.lat, jobById.get(selectedJob)!.location.lon]}
              radius={13}
              interactive={false}
              pathOptions={{ color: "#f2c230", weight: 4, fill: false }}
            />
          )}
        </MapContainer>
      </div>

      <dl className="strip">
        <div className={p.isBest("coverage") ? "best" : ""}>
          <dt>Jobs covered</dt>
          <dd>{m ? `${m.jobs_assigned}/${m.jobs_total}` : "-"}</dd>
        </div>
        <div>
          <dt>Critical covered</dt>
          <dd>{m ? `${m.critical_coverage_pct}%` : "-"}</dd>
        </div>
        <div className={p.isBest("travel") ? "best" : ""}>
          <dt>Driving</dt>
          <dd>{m ? `${Math.round(m.total_travel_km)} km` : "-"}</dd>
        </div>
        <div className={p.isBest("objective") ? "best" : ""}>
          <dt>Total cost</dt>
          <dd>{m ? Math.round(m.objective).toLocaleString() : "-"}</dd>
        </div>
      </dl>
    </section>
  );
}
