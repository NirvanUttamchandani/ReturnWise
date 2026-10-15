import { api } from "../lib/api";
import { useAsync } from "../lib/useAsync";
import PipelineRail from "../components/PipelineRail";
import { Badge, Card, ErrorState, LoadingBlock } from "../components/ui";
import RequestScoped from "./RequestScoped";

function Timeline({ id, outcome }: { id: string; outcome: { label: string; tone: "ok" | "warn" | "bad" | "info" | "idle" } }) {
  const steps = useAsync(() => api.executions(id), [id]);
  if (steps.loading && !steps.data) return <Card><LoadingBlock label="Loading execution log" /></Card>;
  if (steps.error) return <Card><ErrorState error={steps.error} onRetry={steps.reload} title="Execution log could not be loaded" /></Card>;
  const list = steps.data?.steps ?? [];
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <span className="text-muted">Final outcome</span><Badge tone={outcome.tone}>{outcome.label}</Badge>
        <span className="text-muted">{list.length} stored execution records, shown in the order they ran</span>
      </div>
      {list.length === 0 ? <Card><p className="p-5 text-sm text-muted">No execution log was stored for this request.</p></Card> : <PipelineRail steps={list} />}
    </div>
  );
}

export default function Workflow() {
  return (
    <RequestScoped title="Agent Workflow" base="/workflow"
      subtitle="The five agents in the order they ran, read from the stored execution log. Select a stage to inspect its input, output and evidence.">
      {(d, id) => <Timeline id={id} outcome={d.outcome} />}
    </RequestScoped>
  );
}
