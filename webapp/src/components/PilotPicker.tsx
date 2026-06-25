import { useEffect, useState } from "react";
import { api, type Config } from "../lib/api";

export default function PilotPicker({ config }: {
  config: Config | null;
}) {
  const [models, setModels] = useState<string[]>([]);
  const [current, setCurrent] = useState("");
  useEffect(() => {
    if (config) { setModels(config.models || [config.driver]); setCurrent(config.driver); }
  }, [config]);
  const swap = async (m: string) => {
    setCurrent(m);
    try { await api.swapPilot(m); } catch {}
  };
  if (!config) return null;
  return (
    <select value={current} onChange={(e) => swap(e.target.value)}
      title="Pilot model"
      className="bg-bg border border-edge rounded-md px-1.5 h-6 text-[11px] text-muted hover:text-txt
                 focus:outline-none focus:border-accent2 max-w-[160px]">
      {models.map((m) => <option key={m} value={m}>{m.split(":").pop()}</option>)}
    </select>
  );
}
