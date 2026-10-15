import { Link } from "react-router-dom";
import type { RequestSummary } from "../lib/api";
import { dateTime, money, reasonLabel } from "../lib/format";
import { Badge } from "./ui";

export default function RequestTable({ rows, compact }: { rows: RequestSummary[]; compact?: boolean }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-left text-sm">
        <caption className="sr-only">Return requests</caption>
        <thead>
          <tr className="border-b border-line text-xs text-muted">
            <th scope="col" className="px-5 py-2.5 font-medium">Request</th>
            <th scope="col" className="px-3 py-2.5 font-medium">Order</th>
            {!compact && <th scope="col" className="px-3 py-2.5 font-medium">Submitted</th>}
            <th scope="col" className="px-3 py-2.5 font-medium">Reason</th>
            <th scope="col" className="px-3 py-2.5 font-medium">Outcome</th>
            {!compact && <th scope="col" className="px-3 py-2.5 text-right font-medium">Amount</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.request_id} className="border-b border-line last:border-0 hover:bg-paper">
              <td className="px-5 py-3">
                <Link to={`/requests/${r.request_id}`} className="font-mono text-[13px] font-medium text-teal-700 hover:underline">{r.request_id}</Link>
                {r.is_test && <span className="ml-2 rounded bg-idle-bg px-1.5 py-0.5 text-[11px] text-idle">Test</span>}
              </td>
              <td className="px-3 py-3 font-mono text-[13px]">{r.order_id}</td>
              {!compact && <td className="num px-3 py-3 text-muted">{dateTime(r.submitted_at)}</td>}
              <td className="px-3 py-3">{reasonLabel(r.reason)}</td>
              <td className="px-3 py-3">
                <Badge tone={r.outcome.tone}>{r.outcome.label}</Badge>
                {r.validation_label && !compact && <p className="mt-1 text-xs text-muted">{r.validation_label}</p>}
              </td>
              {!compact && <td className="num px-3 py-3 text-right">{r.refund_amount === null ? <span className="text-muted">None</span> : money(r.refund_amount)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
