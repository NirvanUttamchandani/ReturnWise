import { Navigate, Route, Routes } from "react-router-dom";
import AppShell from "./components/AppShell";
import History from "./pages/History";
import NewReturn from "./pages/NewReturn";
import Overview from "./pages/Overview";
import RequestDetailPage from "./pages/RequestDetailPage";
import Resolution from "./pages/Resolution";
import TestingLab from "./pages/TestingLab";
import Workflow from "./pages/Workflow";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Overview />} />
        <Route path="new" element={<NewReturn />} />
        <Route path="workflow" element={<Workflow />} />
        <Route path="workflow/:id" element={<Workflow />} />
        <Route path="resolution" element={<Resolution />} />
        <Route path="resolution/:id" element={<Resolution />} />
        <Route path="requests" element={<History />} />
        <Route path="requests/:id" element={<RequestDetailPage />} />
        <Route path="lab" element={<TestingLab />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
