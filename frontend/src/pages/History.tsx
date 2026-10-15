import { useSearchParams } from "react-router-dom";
import { Search } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useAsync, useDebounced } from "../lib/useAsync";
import RequestTable from "../components/RequestTable";
import { Button, Card, EmptyState, ErrorState, LoadingBlock, PageHeader, inputCls } from "../components/ui";

const PAGE = 15;

export default function History() {
  // Filters live in the URL, so a refresh or a shared link shows the same view.
  const [sp, setSp] = useSearchParams();
  const status = sp.get("status") ?? "";
  const action = sp.get("action") ?? "";
  const tests = sp.get("tests") === "1";
  const offset = Math.max(0, Number(sp.get("offset") ?? 0) || 0);
  const [q, setQ] = useState(sp.get("q") ?? "");
  const dq = useDebounced(q);

  const set = (patch: Record<string, string>) => {
    const next = new URLSearchParams(sp);
    Object.entries(patch).forEach(([k, v]) => (v ? next.set(k, v) : next.delete(k)));
    if (!("offset" in patch)) next.delete("offset");
    setSp(next, { replace: true });
  };
  useEffect(() => { if ((sp.get("q") ?? "") !== dq) set({ q: dq }); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [dq]);

  const meta = useAsync(() => api.meta(), []);
  const list = useAsync(() => api.listRequests({ q: sp.get("q") ?? "", status, action, include_tests: tests, limit: PAGE, offset }), [sp.toString()]);
  const total = list.data?.total ?? 0;
  const filtered = !!(sp.get("q") || status || action);

  return (
    <>
      <PageHeader title="Request History" subtitle="Every stored request. Open one to see its full result and agent timeline." />
      <Card>
        <div className="flex flex-wrap gap-3 border-b border-line px-5 py-3">
          <div className="relative min-w-52 flex-1">
            <Search className="pointer-events-none absolute left-3 top-2.5 size-4 text-muted" aria-hidden />
            <input aria-label="Search requests" placeholder="Search by request or order ID" value={q} onChange={(e) => setQ(e.target.value)} className={`${inputCls()} pl-9`} />
          </div>
          <select aria-label="Filter by status" value={status} onChange={(e) => set({ status: e.target.value })} className={`${inputCls()} sm:w-52`}>
            <option value="">All statuses</option>{meta.data?.statuses.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
          <select aria-label="Filter by action" value={action} onChange={(e) => set({ action: e.target.value })} className={`${inputCls()} sm:w-52`}>
            <option value="">All actions</option>{meta.data?.actions.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
          </select>
          <label className="flex items-center gap-2 text-sm text-muted">
            <input type="checkbox" checked={tests} onChange={(e) => set({ tests: e.target.checked ? "1" : "" })} className="size-4 accent-teal-600" />Include test runs
          </label>
        </div>

        {list.loading && !list.data ? <LoadingBlock label="Loading requests" />
          : list.error ? <ErrorState error={list.error} onRetry={list.reload} title="Requests could not be loaded" />
          : list.data && list.data.items.length === 0
            ? <EmptyState title={filtered ? "No requests match these filters" : "No return requests yet"}
                body={filtered ? "Clear a filter or change the search text." : "Submitted returns will be listed here."}
                action={filtered ? <Button onClick={() => { setQ(""); setSp({}, { replace: true }); }}>Clear filters</Button> : undefined} />
            : list.data && (
              <>
                <RequestTable rows={list.data.items} />
                <div className="flex items-center justify-between border-t border-line px-5 py-3 text-sm text-muted">
                  <span className="num">{offset + 1} to {Math.min(offset + PAGE, total)} of {total}</span>
                  <div className="flex gap-2">
                    <Button disabled={offset === 0} onClick={() => set({ offset: String(Math.max(0, offset - PAGE)) })}>Previous</Button>
                    <Button disabled={offset + PAGE >= total} onClick={() => set({ offset: String(offset + PAGE) })}>Next</Button>
                  </div>
                </div>
              </>)}
      </Card>
    </>
  );
}
