import { useEffect, useState } from "react";
import { AlertOctagon, CheckCircle2, CircleSlash, CornerDownLeft, Search, ShieldCheck, ClipboardList, Scale, Wrench, XCircle } from "lucide-react";
import type { ExecutionStep } from "../lib/api";
import { cx } from "./ui";
import { dateTime } from "../lib/format";
import type { LucideIcon } from "lucide-react";

const STAGES: { order: number; short: string; icon: LucideIcon }[] = [
  { order: 1, short: "Intake and Planning", icon: ClipboardList },
  { order: 2, short: "Order and Policy Research", icon: Search },
  { order: 3, short: "Eligibility Evaluation", icon: Scale },
  { order: 4, short: "Resolution", icon: Wrench },
  { order: 5, short: "Validation (Critic)", icon: ShieldCheck },
];

type Look = { ring: string; chip: string; label: string; icon: LucideIcon };
function look(step: ExecutionStep | undefined): Look {
  if (!step) return { ring: "border-dashed border-line-strong bg-paper text-muted", chip: "bg-idle-bg text-idle", label: "Not run", icon: CircleSlash };
  if (step.status === "error") return { ring: "border-bad bg-bad-bg/40", chip: "bg-bad-bg text-bad", label: "Error", icon: AlertOctagon };
  if (step.status === "skipped" || step.step_type === "skipped")
    return { ring: "border-dashed border-line-strong bg-paper text-muted", chip: "bg-idle-bg text-idle", label: "Skipped", icon: CircleSlash };
  if (step.verdict === "failed") return { ring: "border-warn bg-warn-bg/50", chip: "bg-warn-bg text-warn", label: "Critic rejected", icon: XCircle };
  if (step.verdict === "passed") return { ring: "border-teal-600 bg-teal-50", chip: "bg-ok-bg text-ok", label: "Passed", icon: CheckCircle2 };
  return { ring: "border-teal-600/60 bg-surface", chip: "bg-ok-bg text-ok", label: "Completed", icon: CheckCircle2 };
}

function Node({ step, name, icon: Icon, order, selected, onSelect }: {
  step?: ExecutionStep; name: string; icon: LucideIcon; order: number; selected: boolean; onSelect: () => void;
}) {
  const l = look(step);
  const Status = l.icon;
  return (
    <button type="button" onClick={onSelect} aria-pressed={selected} aria-controls="stage-detail"
      className={cx("flex h-full w-full flex-col rounded-xl border-2 p-3 text-left transition-shadow hover:shadow-card", l.ring, selected && "ring-2 ring-navy-900 ring-offset-2 ring-offset-paper")}>
      <span className="flex items-center justify-between">
        <span className="grid size-8 place-items-center rounded-lg bg-navy-900 text-white"><Icon className="size-4" aria-hidden /></span>
        <span className="num text-xs text-muted">Step {order}</span>
      </span>
      <span className="mt-2 text-sm font-semibold text-ink">{name}</span>
      <span className={cx("mt-2 inline-flex w-fit items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium", l.chip)}>
        <Status className="size-3.5" aria-hidden />{l.label}
      </span>
      {step?.output_summary && <span className="mt-2 line-clamp-2 text-xs text-muted">{step.output_summary}</span>}
    </button>
  );
}

function Json({ title, value }: { title: string; value: unknown }) {
  if (value === null || value === undefined) return null;
  return (
    <details className="rounded-lg border border-line bg-paper">
      <summary className="cursor-pointer px-3 py-2 text-sm font-medium text-ink">{title}</summary>
      <pre className="max-h-72 overflow-auto border-t border-line px-3 py-2 font-mono text-xs leading-relaxed text-ink">{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}

function Detail({ step }: { step: ExecutionStep | undefined }) {
  if (!step) return <p className="text-sm text-muted">This stage has no stored execution record.</p>;
  const out = (step.output ?? {}) as Record<string, unknown>;
  const checks = (out.checks_performed as { check: string; passed: boolean; detail: string }[] | undefined) ?? [];
  const errors = (out.detected_errors as string[] | undefined) ?? [];
  const evidence = (out.evidence as string[] | undefined) ?? (out.supporting_evidence as string[] | undefined) ?? [];
  const fault = out.fault_injected as string | undefined;
  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-base font-semibold text-ink">{step.agent_name}</h3>
        <p className="mt-0.5 text-xs text-muted">{step.agent_role} &middot; <span className="num">{dateTime(step.executed_at)}</span></p>
      </div>
      {fault && <p className="rounded-lg bg-info-bg px-3 py-2 text-sm text-info">Test fault injected for this run: <span className="font-mono">{fault}</span>. This is a controlled demonstration, not a customer scenario.</p>}
      {step.explanation && <p className="text-sm leading-relaxed text-ink">{step.explanation}</p>}
      <dl className="grid gap-3 text-sm sm:grid-cols-2">
        <div><dt className="text-xs text-muted">Input</dt><dd className="mt-0.5 text-ink">{step.input_summary || "None recorded"}</dd></div>
        <div><dt className="text-xs text-muted">Output</dt><dd className="mt-0.5 text-ink">{step.output_summary || "None recorded"}</dd></div>
      </dl>
      {errors.length > 0 && (
        <div><h4 className="mb-1 text-sm font-medium text-bad">Errors detected by the Critic</h4>
          <ul className="list-disc space-y-1 pl-5 text-sm text-ink">{errors.map((e) => <li key={e}>{e}</li>)}</ul></div>
      )}
      {checks.length > 0 && (
        <div><h4 className="mb-1 text-sm font-medium text-ink">Validation checks ({checks.filter((c) => c.passed).length} of {checks.length} passed)</h4>
          <ul className="divide-y divide-line rounded-lg border border-line">
            {checks.map((c) => (
              <li key={c.check} className="flex gap-2.5 px-3 py-2 text-sm">
                {c.passed ? <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-ok" aria-label="Passed" /> : <XCircle className="mt-0.5 size-4 shrink-0 text-bad" aria-label="Failed" />}
                <span><span className="font-mono text-xs text-muted">{c.check}</span><br />{c.detail}</span>
              </li>))}
          </ul></div>
      )}
      {evidence.length > 0 && (
        <div><h4 className="mb-1 text-sm font-medium text-ink">Evidence</h4>
          <ul className="list-disc space-y-0.5 pl-5 text-sm text-ink">{evidence.map((e) => <li key={e}>{e}</li>)}</ul></div>
      )}
      <div className="space-y-2"><Json title="Full input (as stored)" value={step.input} /><Json title="Full output (as stored)" value={step.output} /></div>
    </div>
  );
}

/** Five canonical stages as a rail; correction + revalidation render as a loop lane when they actually ran. */
export default function PipelineRail({ steps }: { steps: ExecutionStep[] }) {
  const byOrder = new Map(steps.map((s) => [s.execution_order, s]));
  const correction = steps.find((s) => s.step_type === "correction");
  const revalidation = steps.find((s) => s.step_type === "revalidation");
  const [selected, setSelected] = useState<number>(() => (steps.find((s) => s.status === "error")?.execution_order ?? 1));
  useEffect(() => { setSelected(steps.find((s) => s.status === "error")?.execution_order ?? 1); }, [steps]);

  return (
    <div>
      <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5" aria-label="Agent pipeline">
        {STAGES.map((st) => (
          <li key={st.order}>
            <Node step={byOrder.get(st.order)} name={st.short} icon={st.icon} order={st.order}
              selected={selected === st.order} onSelect={() => setSelected(st.order)} />
          </li>
        ))}
      </ol>

      {correction && (
        <div className="mt-4 rounded-xl border border-warn/40 bg-warn-bg/30 p-4" aria-label="Correction loop">
          <p className="mb-3 flex items-center gap-2 text-sm font-semibold text-warn">
            <CornerDownLeft className="size-4" aria-hidden />Correction loop: the Critic rejected the first recommendation (one correction attempt allowed)
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            <Node step={correction} name="Resolution (correction)" icon={Wrench} order={correction.execution_order}
              selected={selected === correction.execution_order} onSelect={() => setSelected(correction.execution_order)} />
            <Node step={revalidation} name="Validation (revalidation)" icon={ShieldCheck} order={revalidation?.execution_order ?? correction.execution_order + 1}
              selected={revalidation ? selected === revalidation.execution_order : false} onSelect={() => revalidation && setSelected(revalidation.execution_order)} />
          </div>
        </div>
      )}

      <div id="stage-detail" role="region" aria-live="polite" aria-label="Stage details" className="mt-5 rounded-xl border border-line bg-surface p-5 shadow-card">
        <Detail step={byOrder.get(selected)} />
      </div>
    </div>
  );
}
