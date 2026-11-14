import type { Facts } from "./api";

export type Field = keyof Facts;
export type Choice = { value: string; label: string };
export type FieldDef = { id: Field; label: string; required?: boolean; kind: "choice" | "date" | "text"; choices?: Choice[] };

export const YES_NO: Choice[] = [{ value: "true", label: "Yes" }, { value: "false", label: "No" }];

/** The facts we show, in order. `required` ones are what the deadline needs. */
export const FIELDS: FieldDef[] = [
  { id: "citizenship_group", label: "Citizenship", required: true, kind: "choice", choices: [
    { value: "eu_eea", label: "EU / EEA citizen" }, { value: "other", label: "Outside the EU / EEA" }, { value: "unknown", label: "Not sure" }] },
  { id: "citizenship_country", label: "Country", kind: "text" },
  { id: "permit_type", label: "Permit", required: true, kind: "choice", choices: [
    { value: "work_based", label: "Work-based permit" }, { value: "specialist_blue_card", label: "Specialist / EU Blue Card" },
    { value: "student", label: "Student permit" }, { value: "family_based", label: "Family-based permit" },
    { value: "permanent", label: "Permanent permit" }, { value: "not_sure", label: "Permit: not sure" }] },
  { id: "years_on_work_permit", label: "Time on a work permit", required: true, kind: "choice", choices: [
    { value: "under_2", label: "2 years or less" }, { value: "over_2", label: "More than 2 years" }, { value: "not_sure", label: "Not sure" }] },
  { id: "job_end_date", label: "Last day of work", required: true, kind: "date" },
  { id: "city", label: "City", kind: "text" },
  { id: "field", label: "Work", kind: "text" },
  { id: "studied_in_finland", label: "Studied in Finland", kind: "choice", choices: YES_NO },
  { id: "family_in_finland", label: "Family in Finland", kind: "choice", choices: YES_NO },
];

export function formatShortDate(iso: string) {
  const d = new Date(iso + (iso.length === 10 ? "T00:00:00" : ""));
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

/** Human text for a fact value, or null if unknown. */
export function display(f: FieldDef, value: unknown): string | null {
  if (value === null || value === undefined || value === "") return null;
  if (f.id === "years_on_work_permit" && typeof value === "number") return `${value} ${value === 1 ? "year" : "years"} on a work permit`;
  if (f.kind === "date") return `Last day ${formatShortDate(String(value))}`;
  if (f.choices === YES_NO) return value === true || value === "true" ? f.label : `Not ${f.label.toLowerCase()}`;
  if (f.choices) return f.choices.find((c) => c.value === String(value))?.label ?? String(value);
  return String(value);
}

export function parse(f: FieldDef, raw: string): Facts[Field] {
  if (raw === "") return null;
  if (f.choices === YES_NO) return raw === "true";
  return raw as Facts[Field];
}
