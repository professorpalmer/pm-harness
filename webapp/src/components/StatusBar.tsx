import { useEffect, useState } from "react";
import { Circle, GitBranch, Boxes, Cpu } from "lucide-react";
import { api, type Config } from "../lib/api";
import { isDesktop } from "../lib/transport";

// Bottom status strip (Hermes shell/statusbar pattern): a thin always-on bar with
// runtime health, active workspace branch, job count, pilot model, and build mode.
export default function StatusBar({ config, jobCount }: {
  config: Config | null; jobCount: number;
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
      <span className="flex items-center gap-1 text-good">
        <Circle size={7} className="fill-good text-good" /> ready
      </span>
      {branch && <span className="flex items-center gap-1"><GitBranch size={10} />{branch}</span>}
      <span className="flex items-center gap-1"><Boxes size={10} />{jobCount} job{jobCount === 1 ? "" : "s"}</span>
      <div className="flex-1" />
      <span className="flex items-center gap-1"><Cpu size={10} />{config?.driver?.split(":").pop() || "pilot"}</span>
      <span>{config?.reach || ""}</span>
      <span className="text-muted/60">{isDesktop ? "desktop" : "web"}</span>
    </div>
  );
}
