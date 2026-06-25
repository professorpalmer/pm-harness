import { useEffect, useState } from "react";
import { Settings as SettingsIcon } from "lucide-react";
import { api, type Settings } from "../lib/api";

export default function SettingsPane() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api.settings()
      .then(setSettings)
      .catch((err) => {
        setError("Failed to load settings");
        console.error(err);
      });
  }, []);

  const update = async (partial: Partial<Settings>) => {
    if (!settings) return;
    setSaving(true);
    setStatus("");
    setError("");
    try {
      const updated = await api.updateSettings(partial);
      setSettings(updated);
      setStatus("saved");
      const timer = setTimeout(() => setStatus(""), 2000);
      return () => clearTimeout(timer);
    } catch (err: any) {
      setError(err?.error || "Failed to update settings");
    } finally {
      setSaving(false);
    }
  };

  if (!settings) {
    return (
      <div className="flex flex-col h-full text-[12px] p-4 text-faint">
        {error ? error : "Loading settings..."}
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full text-[12px]">
      <div className="flex items-center justify-between px-3 py-2 border-b border-edge">
        <span className="uppercase tracking-wider text-[10px] text-faint font-medium flex items-center gap-1.5">
          <SettingsIcon size={11} /> Settings
        </span>
        <div className="flex items-center gap-2">
          {status && <span className="text-good text-[10px] font-medium">{status}</span>}
          {error && <span className="text-risk text-[10px] font-medium">{error}</span>}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {/* Driver Select */}
        <div className="space-y-1.5">
          <label className="block uppercase tracking-wider text-[10px] text-faint font-semibold">
            Driver (Model)
          </label>
          <select
            value={settings.driver}
            onChange={(e) => update({ driver: e.target.value })}
            disabled={saving}
            className="w-full bg-panel2 border border-edge rounded px-2.5 py-1.5 text-txt focus:outline-none focus:border-accent disabled:opacity-50"
          >
            {settings.models.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
          <p className="text-[10px] text-muted">
            The pilot model driver. Changes take effect live on the chat session.
          </p>
        </div>

        {/* Budget Stepper / Number */}
        <div className="space-y-1.5">
          <label className="block uppercase tracking-wider text-[10px] text-faint font-semibold">
            Budget (Steps)
          </label>
          <div className="flex items-center gap-2">
            <input
              type="number"
              min="1"
              max="50"
              value={settings.budget}
              onChange={(e) => {
                const val = parseInt(e.target.value);
                if (!isNaN(val)) {
                  update({ budget: val });
                }
              }}
              disabled={saving}
              className="w-20 bg-panel2 border border-edge rounded px-2.5 py-1 text-txt focus:outline-none focus:border-accent disabled:opacity-50 font-mono"
            />
            <span className="text-[10px] text-muted">steps per run (1-50)</span>
          </div>
          <p className="text-[10px] text-muted">
            Maximum Orchestration steps/budget allocated per task execution.
          </p>
        </div>

        {/* Auto Distill Toggle */}
        <div className="space-y-1.5">
          <label className="block uppercase tracking-wider text-[10px] text-faint font-semibold">
            Auto-Distill
          </label>
          <button
            onClick={() => update({ auto_distill: !settings.auto_distill })}
            disabled={saving}
            className={`w-full flex items-center justify-between px-3 py-2 rounded border transition text-left ${
              settings.auto_distill
                ? "bg-accent/10 border-accent/30 text-accent"
                : "bg-panel2 border-edge text-muted"
            } disabled:opacity-50`}
          >
            <span className="font-medium text-[11px]">Propose skills/rules after task</span>
            <span className="text-[10px] uppercase font-bold tracking-wider">
              {settings.auto_distill ? "on" : "off"}
            </span>
          </button>
          <p className="text-[10px] text-muted">
            When enabled, PM proposes pending skill/rule candidates automatically on task completion.
          </p>
        </div>

        {/* Read-Only Info */}
        <div className="border-t border-edge pt-3 space-y-2.5">
          <div className="uppercase tracking-wider text-[10px] text-faint font-semibold">
            System Info
          </div>

          <div className="grid grid-cols-3 gap-1">
            <span className="text-faint">Reach:</span>
            <span className="col-span-2 text-muted font-mono select-all break-all bg-panel2 px-1 py-0.5 rounded border border-edge/30 inline-block w-fit">
              {settings.reach}
            </span>
          </div>

          {settings.wiki_auto !== undefined && (
            <div className="grid grid-cols-3 gap-1">
              <span className="text-faint">Wiki Auto:</span>
              <span className="col-span-2 text-muted font-mono inline-block w-fit">
                {settings.wiki_auto ? "yes" : "no"}
              </span>
            </div>
          )}

          <div className="space-y-0.5">
            <div className="text-faint">State Directory:</div>
            <div className="text-muted font-mono select-all break-all bg-panel2 p-1.5 rounded border border-edge/30 text-[11px]">
              {settings.state_dir || "Temporary (per-session)"}
            </div>
          </div>

          <div className="space-y-0.5">
            <div className="text-faint">Repository:</div>
            <div className="text-muted font-mono select-all break-all bg-panel2 p-1.5 rounded border border-edge/30 text-[11px]">
              {settings.repo || "None"}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
