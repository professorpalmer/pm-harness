import { useState } from "react";
import { Database, Globe } from "lucide-react";
import StatePane from "./StatePane";
import BrowserPane from "./BrowserPane";

type Tab = "state" | "browser";

export default function RightPane({ artifacts }: {
  artifacts: { type: string; headline: string; confidence?: number }[];
}) {
  const [tab, setTab] = useState<Tab>("state");
  return (
    <aside className="bg-panel border-l border-edge flex flex-col h-full overflow-hidden">
      <div className="flex border-b border-edge">
        <TabBtn active={tab === "state"} onClick={() => setTab("state")} icon={<Database size={12} />} label="State" />
        <TabBtn active={tab === "browser"} onClick={() => setTab("browser")} icon={<Globe size={12} />} label="Browser" />
      </div>
      <div className="flex-1 overflow-hidden">
        {tab === "state" ? <StatePane artifacts={artifacts} embedded /> : <BrowserPane />}
      </div>
    </aside>
  );
}

function TabBtn({ active, onClick, icon, label }: any) {
  return (
    <button onClick={onClick}
      className={`flex-1 flex items-center justify-center gap-1.5 py-2 text-[11px] uppercase tracking-wider transition
        ${active ? "text-txt border-b-2 border-accent bg-panel2/50" : "text-muted hover:text-txt"}`}>
      {icon}{label}
    </button>
  );
}
