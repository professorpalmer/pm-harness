import { useState } from "react";
import { X, Cpu, SlidersHorizontal, Info } from "lucide-react";
import ModelsSettingsPage from "./ModelsSettingsPage";
import SettingsPane from "./SettingsPane";

type PageId = "models" | "general" | "about";

const NAV: { id: PageId; label: string; icon: any }[] = [
  { id: "models", label: "Models", icon: Cpu },
  { id: "general", label: "General", icon: SlidersHorizontal },
  { id: "about", label: "About", icon: Info },
];

// Full-screen settings overlay with a left sidebar nav and a routed content
// area (Cursor/Hermes-style), replacing the cramped single side-panel. New
// focused pages live as their own components; the legacy consolidated panel is
// reachable under "General" until each section is split out.
export default function SettingsShell({
  onClose,
  onOpenWizard,
}: {
  onClose: () => void;
  onOpenWizard: () => void;
}) {
  const [page, setPage] = useState<PageId>("models");

  return (
    <div className="fixed inset-0 z-50 bg-bg flex flex-col">
      {/* top bar */}
      <div className="flex items-center justify-between px-4 h-11 border-b border-edge/40 shrink-0">
        <span className="text-[13px] font-semibold text-txt">Settings</span>
        <button
          onClick={onClose}
          title="Close settings"
          className="p-1.5 rounded-md text-muted hover:text-txt hover:bg-panel2 transition"
        >
          <X size={16} />
        </button>
      </div>

      <div className="flex flex-1 min-h-0">
        {/* sidebar */}
        <div className="w-52 shrink-0 border-r border-edge/40 py-3 px-2 flex flex-col gap-0.5 overflow-y-auto">
          {NAV.map((item) => {
            const Icon = item.icon;
            const active = page === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setPage(item.id)}
                className={`flex items-center gap-2.5 px-2.5 py-1.5 rounded-md text-[12.5px] text-left transition
                  ${active ? "bg-panel2 text-txt font-medium" : "text-muted hover:text-txt hover:bg-panel2/50"}`}
              >
                <Icon size={14} className={active ? "text-accent" : "text-faint"} />
                {item.label}
              </button>
            );
          })}
        </div>

        {/* content */}
        <div className="flex-1 min-w-0 overflow-y-auto px-8 py-6">
          {page === "models" && <ModelsSettingsPage />}
          {page === "general" && <SettingsPane onOpenWizard={onOpenWizard} />}
          {page === "about" && (
            <div className="max-w-2xl text-[12px] text-muted">
              <h2 className="text-[15px] font-semibold text-txt mb-2">About</h2>
              <p>Marionette -- a desktop AI coding harness over Puppetmaster durable state.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
