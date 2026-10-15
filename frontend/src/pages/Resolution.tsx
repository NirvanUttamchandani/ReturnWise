import ResolutionView from "../components/ResolutionView";
import RequestScoped from "./RequestScoped";

export default function Resolution() {
  return (
    <RequestScoped title="Resolution Center" base="/resolution"
      subtitle="The final recommendation, the policy evidence behind it and the Critic's independent checks.">
      {(d) => <ResolutionView d={d} />}
    </RequestScoped>
  );
}
