import { useEffect, useState } from "react";
import { Circle, GitBranch, Boxes, Cpu, PanelLeft, PanelRight } from "lucide-react";
import { api, type Config } from "../lib/api";
import { isDesktop } from "../lib/transport";

// Bottom status strip (Hermes shell/statusbar pattern): runtime health, active
// workspace branch, job count, pilot model, build mode, and panel toggles.
export default function StatusBar({ config, jobCount, leftOpen, rightOpen, onToggleLeft, onToggleRight }: {
  config: Config | null; jobCount: number;
  leftOpen: boolean; rightOpen: boolean;
  onToggleLeft: () => void; onToggleRight: () => void;
}) {
  const [branch, setBranch] = useState("");
  useEffect(() => {
    api.workspaces().then((ws) => {
      const active = ws.find((w) => w.active);
      if (active) setBranch(active.name);
    }).catch(() => {});
  }, [config]);

  return (
    <div className="flex items-center gap-3 px-3 h-6 border-t border-edge bg-panel text-[10px] text-muted select-none">
      <button onClick={onToggleLeft} title="Toggle sessions panel (Cmd+B)"
        className={`p-0.5 rounded hover:bg-panel2 ${leftOpen ? "text-txt" : "text-muted"}`}><PanelLeft size={12} /></button>
      <button onClick={onToggleRight} title="Toggle right panel (Cmd+J)"
        className={`p-0.5 rounded hover:bg-panel2 ${rightOpen ? "text-txt" : "text-muted"}`}><PanelRight size={12} /></button>
      <span className="w-px h-3 bg-edge" />
      <span className="flex items-center gap-1 text-good"><Circle size={7} className="fill-good text-good" /> ready</span>
      {branch && <span className="flex items-center gap-1"><GitBranch size={10} />{branch}</span>}
      <span className="flex items-center gap-1"><Boxes size={10} />{jobCount} job{jobCount === 1 ? "" : "s"}</span>
      <div className="flex-1" />
      <span className="flex items-center gap-1"><Cpu size={10} />{config?.driver?.split(":").pop() || "pilot"}</span>
      <span>{config?.reach || ""}</span>
      <span className="text-muted/60">{isDesktop ? "desktop" : "web"}</span>
    </div>
  );
}
