import type { Priority } from "./types";

export const fmtTime = (m: number) =>
  `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;

export const PRIORITY_LABEL: Record<Priority, string> = { 1: "Normal", 2: "High", 3: "Critical" };
export const PRIORITY_COLOR: Record<Priority, string> = { 1: "#2f6e9e", 2: "#b86e00", 3: "#c8102e" };

// Distinct, map-legible route colours, one per technician.
const ROUTE_COLORS = [
  "#1b7f79", "#6a4c93", "#2f6e9e", "#9c4f2e", "#4d7c0f", "#a3376b",
  "#0e7490", "#7c5c1e", "#5b5fc7", "#3f6212", "#b4415a", "#386fa4",
];
export const techColor = (index: number) => ROUTE_COLORS[index % ROUTE_COLORS.length];

export const skillLabel = (s: string) => s.replace("_", " ");
