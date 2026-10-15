import type { ReactNode } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { api, type RequestDetail } from "../lib/api";
import { useAsync } from "../lib/useAsync";
import RequestPicker from "../components/RequestPicker";
import { Button, Card, EmptyState, ErrorState, LoadingBlock, PageHeader } from "../components/ui";

/** Shared frame for pages that inspect one stored request (id in the URL, so refresh keeps it). */
export default function RequestScoped({ title, subtitle, base, children }: {
  title: string; subtitle: string; base: "/workflow" | "/resolution"; children: (d: RequestDetail, id: string) => ReactNode;
}) {
  const { id } = useParams();
  const latest = useAsync(() => (id ? Promise.resolve(null) : api.listRequests({ include_tests: true, limit: 1 })), [id]);
  const detail = useAsync(() => (id ? api.request(id) : Promise.resolve(null)), [id]);

  if (!id) {
    if (latest.loading) return <><PageHeader title={title} subtitle={subtitle} /><Card><LoadingBlock /></Card></>;
    if (latest.error) return <><PageHeader title={title} subtitle={subtitle} /><Card><ErrorState error={latest.error} onRetry={latest.reload} /></Card></>;
    const first = latest.data?.items[0];
    if (first) return <Navigate to={`${base}/${first.request_id}`} replace />;
    return <><PageHeader title={title} subtitle={subtitle} /><Card><EmptyState title="No requests to show yet" body="Submit a return request and its result will appear here." action={<Link to="/new"><Button variant="primary">Create a return request</Button></Link>} /></Card></>;
  }
  return (
    <>
      <PageHeader title={title} subtitle={subtitle} actions={<RequestPicker current={id} base={base} />} />
      {detail.loading && !detail.data ? <Card><LoadingBlock /></Card>
        : detail.error ? <Card><ErrorState error={detail.error} onRetry={detail.reload}
            title={detail.error.status === 404 ? "Request not found" : "Request could not be loaded"} /></Card>
        : detail.data && children(detail.data, id)}
    </>
  );
}
