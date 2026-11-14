import type { PlanResponse, Source } from "./api";

/** One numbered step, shown as just "Step n" (no week labels). The order matches the backend's /steps/update
 *  numbering exactly: the plan's 3 first actions, then its later steps (skipping "Week 1", which repeats the
 *  first actions), then the backup permit options. */
export type StepItem = {
  n: number;
  key: string; // stable id, for "done" ticks
  kind: "action" | "week" | "backup";
  title: string;
  why?: string;
  points: string[];
  sources: Source[];
};

export function flattenSteps(plan?: PlanResponse): StepItem[] {
  if (!plan) return [];
  const out: Omit<StepItem, "n">[] = [
    ...plan.this_week.map((a, i) => ({
      key: `a${i}:${a.title}`, kind: "action" as const, title: a.title, why: a.why, points: a.how, sources: a.sources,
    })),
    ...plan.timeline.filter((w) => w.week.trim().toLowerCase() !== "week 1").map((w) => ({
      key: `w:${w.week}:${w.steps[0] ?? ""}`, kind: "week" as const, title: w.steps[0] ?? w.week,
      points: w.steps.slice(1), sources: w.sources,
    })),
    ...plan.plan_b.map((p) => ({
      key: `b:${p.id || p.option}`, kind: "backup" as const, title: p.option, why: p.why,
      points: p.who_it_fits ? [`Who it fits: ${p.who_it_fits}`] : [], sources: p.sources,
    })),
  ];
  return out.map((s, i) => ({ ...s, n: i + 1 }));
}
