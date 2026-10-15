import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { dateTime } from "../lib/format";
import { useAsync } from "../lib/useAsync";
import { inputCls } from "./ui";

/** Lets the user choose which stored request to inspect. The selection lives in the URL so a refresh keeps it. */
export default function RequestPicker({ current, base }: { current?: string; base: string }) {
  const nav = useNavigate();
  const { data } = useAsync(() => api.listRequests({ include_tests: true, limit: 50 }), []);
  const items = data?.items ?? [];
  const options = current && !items.some((i) => i.request_id === current) ? [{ request_id: current, order_id: "", submitted_at: "", outcome: { label: "" } }, ...items] : items;
  return (
    <div className="w-full sm:w-80">
      <label htmlFor="req-picker" className="mb-1 block text-xs font-medium text-muted">Request</label>
      <select id="req-picker" className={inputCls()} value={current ?? ""} onChange={(e) => nav(`${base}/${e.target.value}`)}>
        {!current && <option value="" disabled>Select a request</option>}
        {options.map((r) => (
          <option key={r.request_id} value={r.request_id}>
            {r.request_id}{r.order_id ? ` · ${r.order_id}` : ""}{r.submitted_at ? ` · ${dateTime(r.submitted_at)}` : ""}
          </option>))}
      </select>
    </div>
  );
}
