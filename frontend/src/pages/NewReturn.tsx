import { useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, Send } from "lucide-react";
import { api, ApiError, type RequestDetail } from "../lib/api";
import { useAsync } from "../lib/useAsync";
import { money } from "../lib/format";
import { Badge, Button, Card, Field, Notice, PageHeader, inputCls } from "../components/ui";

const newToken = () => (globalThis.crypto?.randomUUID?.() ?? `t-${Date.now()}-${Math.random().toString(16).slice(2)}`);

export default function NewReturn() {
  const meta = useAsync(() => api.meta(), []);
  const orders = useAsync(() => api.orders(), []);
  const [orderId, setOrderId] = useState("");
  const [reason, setReason] = useState("");
  const [description, setDescription] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [failure, setFailure] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<RequestDetail | null>(null);
  // One token per form attempt: a repeated click or a retry after a network drop cannot create a second request.
  const token = useRef(newToken());
  const max = meta.data?.max_description_length ?? 500;
  const picked = useMemo(() => orders.data?.orders.find((o) => o.order_id === orderId.trim().toUpperCase()), [orders.data, orderId]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    const local: Record<string, string> = {};
    if (!orderId.trim()) local.order_id = "Enter an order ID, for example ORD-001.";
    if (!reason) local.reason = "Choose the reason for the return.";
    if (description.length > max) local.description = `Keep the description under ${max} characters.`;
    setErrors(local); setFailure(null);
    if (Object.keys(local).length) return;
    setBusy(true);
    try {
      setResult(await api.createRequest({ order_id: orderId.trim(), reason, description: description.trim(), client_token: token.current }));
    } catch (err) {
      const apiErr = err instanceof ApiError ? err : new ApiError(0, "unknown", "Something unexpected happened.");
      if (apiErr.status === 422 && Object.keys(apiErr.fields).length) setErrors(apiErr.fields); else setFailure(apiErr);
    } finally { setBusy(false); }
  }

  function reset() {
    token.current = newToken();
    setResult(null); setOrderId(""); setReason(""); setDescription(""); setErrors({}); setFailure(null);
  }

  if (result) {
    const rec = result.recommendation;
    return (
      <>
        <PageHeader title="New Return" />
        <Card className="max-w-2xl">
          <div className="space-y-5 p-6">
            <div className="flex items-start gap-3">
              <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-ok" aria-hidden />
              <div>
                <h2 className="text-base font-semibold">{result.duplicate ? "This request was already submitted" : "Request saved and processed"}</h2>
                <p className="mt-1 text-sm text-muted">Request ID <span data-testid="request-id" className="font-mono font-semibold text-ink">{result.request.request_id}</span></p>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Badge tone={result.outcome.tone}>{result.outcome.label}</Badge>
              {rec && <span className="text-sm text-ink">{rec.action_label}{rec.refund_amount !== null && <> of <span className="num font-semibold">{money(rec.refund_amount)}</span></>}</span>}
              {rec && <span className="text-sm text-muted">{rec.validation_label}</span>}
            </div>
            {!rec && <Notice tone="bad" title="No recommendation was produced">{result.request.error_message}</Notice>}
            <Notice tone="info">This is a recommendation. No refund has been paid and no customer has been notified.</Notice>
            <div className="flex flex-wrap gap-3">
              <Link to={`/resolution/${result.request.request_id}`}><Button variant="primary">View resolution</Button></Link>
              <Link to={`/workflow/${result.request.request_id}`}><Button>View agent workflow</Button></Link>
              <Button variant="ghost" onClick={reset}>Submit another return</Button>
            </div>
          </div>
        </Card>
      </>
    );
  }

  return (
    <>
      <PageHeader title="New Return" subtitle="Five agents review the request against the store policy. The result is a recommendation only." />
      <Card className="max-w-2xl">
        <form onSubmit={submit} noValidate className="space-y-5 p-6" aria-describedby="form-note">
          <Field id="order_id" label="Order ID" error={errors.order_id}
            hint={picked ? `${picked.product_name} · ${picked.status} · ${money(picked.total_amount)}` : "Pick a sample order or type any order ID."}>
            <input id="order_id" list="order-options" value={orderId} onChange={(e) => setOrderId(e.target.value)} autoComplete="off" placeholder="ORD-001"
              aria-invalid={!!errors.order_id} aria-describedby={errors.order_id ? "order_id-error" : "order_id-hint"} className={inputCls(!!errors.order_id)} />
            <datalist id="order-options">
              {orders.data?.orders.map((o) => <option key={o.order_id} value={o.order_id}>{o.product_name}</option>)}
            </datalist>
          </Field>

          <Field id="reason" label="Reason for return" error={errors.reason}>
            <select id="reason" value={reason} onChange={(e) => setReason(e.target.value)} aria-invalid={!!errors.reason} className={inputCls(!!errors.reason)}>
              <option value="" disabled>Choose a reason</option>
              {meta.data?.reasons.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
            </select>
          </Field>

          <Field id="description" label="Description (optional)" error={errors.description} hint={`${description.length} of ${max} characters`}>
            <textarea id="description" rows={4} value={description} onChange={(e) => setDescription(e.target.value)} aria-invalid={!!errors.description}
              className={inputCls(!!errors.description)} placeholder="Anything that helps the reviewer. Treated as plain text, never as instructions." />
          </Field>

          {failure && (
            <Notice tone="bad" title={failure.code === "persistence_failed" ? "The request was not recorded as completed" : "The request could not be submitted"}>
              {failure.message}{failure.requestId && <> Reference: <span className="font-mono">{failure.requestId}</span>.</>}
              {failure.status === 0 && " Your entries are kept. Submitting again will not create a duplicate."}
            </Notice>)}

          <div className="flex flex-wrap items-center gap-4 border-t border-line pt-5">
            <Button type="submit" variant="primary" loading={busy}><Send className="size-4" aria-hidden />{busy ? "Processing" : "Submit return"}</Button>
            <p id="form-note" className="text-xs text-muted">ReturnWise recommends actions. It does not issue refunds.</p>
          </div>
        </form>
      </Card>
    </>
  );
}
