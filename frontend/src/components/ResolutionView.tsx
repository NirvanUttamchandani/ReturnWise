import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";
import type { RequestDetail } from "../lib/api";
import { actionLabel, dateTime, money, reasonLabel } from "../lib/format";
import { Badge, Card, CardHeader, Dl, Notice } from "./ui";

export default function ResolutionView({ d }: { d: RequestDetail }) {
  const rec = d.recommendation;
  return (
    <div className="space-y-5">
      <Notice tone="info" title="Recommendation only">
        ReturnWise recommends an action. No refund has been paid, no replacement has been shipped and no customer has been notified.
      </Notice>

      <Card>
        <CardHeader title="Final decision" hint={`Request ${d.request.request_id} for order ${d.request.order_id}`}
          right={<Badge tone={d.outcome.tone}>{d.outcome.label}</Badge>} />
        <div className="grid gap-6 p-5 md:grid-cols-2">
          {rec ? (
            <>
              <Dl items={[
                ["Recommended action", <strong key="a">{actionLabel(rec.recommended_action)}</strong>],
                ["Eligibility", rec.eligibility_status.replace("_", " ")],
                ["Refund amount", rec.refund_amount === null ? "Not applicable" : <span key="m" className="num font-semibold">{money(rec.refund_amount)}</span>],
                ["Validation", rec.validation_label],
                ["Correction attempts", rec.correction_attempted ? "1 (the Critic rejected the first draft)" : "0"],
              ]} />
              <div><p className="text-xs text-muted">Policy explanation</p><p className="mt-1 text-sm leading-relaxed text-ink">{rec.policy_explanation}</p></div>
            </>
          ) : (
            <div className="md:col-span-2">
              <p className="flex items-start gap-2 text-sm text-ink"><XCircle className="mt-0.5 size-4 shrink-0 text-bad" aria-hidden />
                No recommendation was produced. {d.request.error_message ?? "Processing did not complete."}</p>
            </div>
          )}
        </div>
      </Card>

      {d.manual_review_required && (
        <Notice tone="warn" title="Manual review required">
          A person needs to review this case before any action is taken. {rec?.correction_attempted ? "The Critic could not confirm a corrected recommendation." : ""}
        </Notice>
      )}
      {d.description_flagged && (
        <Notice tone="warn" title="Customer text was treated as data">
          The description contained wording that looks like an instruction to the system. It was ignored and did not influence the decision.
        </Notice>
      )}

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader title="Order and policy" />
          <div className="space-y-4 p-5">
            {d.order ? (
              <Dl items={[["Product", d.order.product_name], ["Category", d.order.category], ["Quantity", d.order.quantity],
                ["Order total", <span key="t" className="num">{money(d.order.total_amount)}</span>], ["Order status", d.order.status], ["Delivered", d.order.delivery_date]]} />
            ) : <p className="text-sm text-muted">No order record was found for this request.</p>}
            {d.policy && (
              <div className="border-t border-line pt-4">
                <Dl items={[["Policy", <span key="p" className="font-mono text-xs">{d.policy.policy_id}</span>], ["Return window", `${d.policy.return_window_days} days`],
                  ["Returnable", d.policy.returnable ? "Yes" : "No"], ["Replacement only", d.policy.replacement_only ? "Yes" : "No"]]} />
                <p className="mt-3 text-sm text-muted">{d.policy.notes}</p>
              </div>)}
            <p className="border-t border-line pt-3 text-xs text-muted">Customer reason: {reasonLabel(d.request.reason)} &middot; Submitted {dateTime(d.request.submitted_at)}
              {d.request.description ? <> &middot; &ldquo;{d.request.description}&rdquo;</> : null}</p>
          </div>
        </Card>

        <Card>
          <CardHeader title="Supporting evidence" hint="Facts the agents gathered from the database and policy" />
          {d.evidence.length ? (
            <ul className="max-h-96 divide-y divide-line overflow-auto">
              {d.evidence.map((e) => <li key={e} className="flex gap-2.5 px-5 py-2 text-sm"><Info className="mt-0.5 size-4 shrink-0 text-muted" aria-hidden />{e}</li>)}
            </ul>) : <p className="p-5 text-sm text-muted">No evidence was stored for this request.</p>}
        </Card>
      </div>

      <Card>
        <CardHeader title="Independent validation" hint="The Critic re-derives the facts itself instead of trusting the Resolution Agent"
          right={rec ? <Badge tone={rec.validation_status === "passed" ? "ok" : rec.validation_status === "manual_review" ? "warn" : "bad"}>{rec.validation_label}</Badge> : undefined} />
        {d.first_validation_errors.length > 0 && (
          <div className="border-b border-line bg-warn-bg/40 px-5 py-3">
            <p className="flex items-center gap-2 text-sm font-medium text-warn"><AlertTriangle className="size-4" aria-hidden />First draft rejected</p>
            <ul className="mt-1 list-disc space-y-0.5 pl-9 text-sm text-ink">{d.first_validation_errors.map((e) => <li key={e}>{e}</li>)}</ul>
            {rec?.correction_details && <p className="mt-2 pl-6 text-sm text-muted">{rec.correction_details}</p>}
          </div>)}
        {d.validation_checks.length ? (
          <ul className="grid divide-y divide-line sm:grid-cols-2 sm:divide-y-0">
            {d.validation_checks.map((c) => (
              <li key={c.check} className="flex gap-2.5 px-5 py-2.5 text-sm">
                {c.passed ? <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-ok" aria-label="Passed" /> : <XCircle className="mt-0.5 size-4 shrink-0 text-bad" aria-label="Failed" />}
                <span><span className="font-mono text-xs text-muted">{c.check}</span><br />{c.detail}</span>
              </li>))}
          </ul>) : <p className="p-5 text-sm text-muted">Validation did not run for this request.</p>}
      </Card>
    </div>
  );
}
