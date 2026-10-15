import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { api } from "../lib/api";
import { useAsync } from "../lib/useAsync";
import PipelineRail from "../components/PipelineRail";
import ResolutionView from "../components/ResolutionView";
import { Card, CardHeader, ErrorState, LoadingBlock, PageHeader } from "../components/ui";

export default function RequestDetailPage() {
  const { id = "" } = useParams();
  const detail = useAsync(() => api.request(id), [id]);
  const steps = useAsync(() => api.executions(id), [id]);
  return (
    <>
      <Link to="/requests" className="mb-3 inline-flex items-center gap-1.5 text-sm font-medium text-teal-700 hover:underline"><ArrowLeft className="size-4" aria-hidden />Request History</Link>
      <PageHeader title={id} subtitle="Stored record, final result and complete agent timeline." />
      {detail.loading && !detail.data ? <Card><LoadingBlock /></Card>
        : detail.error ? <Card><ErrorState error={detail.error} onRetry={detail.reload} title={detail.error.status === 404 ? "Request not found" : "Request could not be loaded"} /></Card>
        : detail.data && (
          <div className="space-y-6">
            <ResolutionView d={detail.data} />
            <Card>
              <CardHeader title="Agent timeline" hint="Everything below was read from the stored execution log" />
              <div className="p-5">
                {steps.loading && !steps.data ? <LoadingBlock /> : steps.error ? <ErrorState error={steps.error} onRetry={steps.reload} />
                  : steps.data && steps.data.steps.length > 0 ? <PipelineRail steps={steps.data.steps} />
                  : <p className="text-sm text-muted">No execution log was stored for this request.</p>}
              </div>
            </Card>
          </div>)}
    </>
  );
}
