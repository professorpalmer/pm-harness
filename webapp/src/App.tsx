import { useEffect, useState } from "react";
import { api, type Config } from "./lib/api";
import LeftRail from "./components/LeftRail";
import Conversation from "./components/Conversation";
import RightPane from "./components/RightPane";
import TaskStack from "./components/TaskStack";
import StatusBar from "./components/StatusBar";

export default function App() {
  const [config, setConfig] = useState<Config | null>(null);
  const [artifacts, setArtifacts] = useState<{ type: string; headline: string; confidence?: number }[]>([]);
  const [jobsRefresh, setJobsRefresh] = useState(0);
  const [jobCount, setJobCount] = useState(0);

  useEffect(() => { api.config().then(setConfig).catch(() => {}); }, []);
  useEffect(() => { api.jobs().then((j) => setJobCount(j.length)).catch(() => {}); }, [jobsRefresh]);

  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 min-h-0 grid" style={{ gridTemplateColumns: "248px 1fr 320px" }}>
        <LeftRail jobsRefresh={jobsRefresh} />
        <Conversation
          config={config}
          onArtifacts={(a) => setArtifacts((prev) => [...a, ...prev])}
          onJobChange={() => setJobsRefresh((n) => n + 1)}
        />
        <RightPane artifacts={artifacts} />
      </div>
      <TaskStack refresh={jobsRefresh} />
      <StatusBar config={config} jobCount={jobCount} />
    </div>
  );
}
