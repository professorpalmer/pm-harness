import { useEffect, useState } from "react";
import { Search, RefreshCw } from "lucide-react";
import { api, type ModelCatalogEntry } from "../lib/api";

// Models settings page: toggle which provider models appear in the pilot picker
// dropdown (Cursor/Hermes-style). Grouped by provider; only providers with a
// present key are shown. The enabled set is persisted server-side and feeds
// /api/pilot picker via model_visibility.enabled_pilots().
export default function ModelsSettingsPage() {
  const [catalog, setCatalog] = useState<ModelCatalogEntry[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.modelCatalog();
      setCatalog(res.catalog || []);
    } catch {
      setCatalog([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const toggle = async (entry: ModelCatalogEntry) => {
    const next = !entry.enabled;
    setBusy(entry.spec);
    // optimistic
    setCatalog((prev) => prev.map((c) => (c.spec === entry.spec ? { ...c, enabled: next } : c)));
    try {
      await api.toggleModel(entry.spec, next);
      // tell the picker to refetch its list
      window.dispatchEvent(new Event("harness-config-changed"));
    } catch {
      // revert on failure
      setCatalog((prev) => prev.map((c) => (c.spec === entry.spec ? { ...c, enabled: !next } : c)));
    } finally {
      setBusy(null);
    }
  };

  const q = query.trim().toLowerCase();
  const filtered = q
    ? catalog.filter((c) => c.model.toLowerCase().includes(q) || c.provider_display.toLowerCase().includes(q))
    : catalog;

  // group by provider, preserving catalog order
  const groups: { provider: string; display: string; items: ModelCatalogEntry[] }[] = [];
  for (const c of filtered) {
    let g = groups.find((x) => x.provider === c.provider);
    if (!g) {
      g = { provider: c.provider, display: c.provider_display, items: [] };
      groups.push(g);
    }
    g.items.push(c);
  }

  const enabledCount = catalog.filter((c) => c.enabled).length;

  return (
    <div className="max-w-2xl">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-[15px] font-semibold text-txt">Models</h2>
          <p className="text-[11px] text-muted mt-0.5">
            Toggle which models appear in the pilot picker. {enabledCount > 0
              ? `${enabledCount} enabled.`
              : "None curated -- the picker shows every available model."}
          </p>
        </div>
        <button
          onClick={load}
          title="Refresh"
          className="p-1.5 rounded-md border border-edge/40 text-muted hover:text-txt hover:bg-panel2 transition"
        >
          <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
        </button>
      </div>

      <div className="flex items-center gap-2 mb-3 px-2.5 py-1.5 rounded-lg bg-panel2 border border-edge/50">
        <Search size={13} className="text-faint shrink-0" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search models or providers"
          className="bg-transparent text-[12px] text-txt placeholder:text-faint outline-none w-full"
        />
      </div>

      {loading && catalog.length === 0 ? (
        <div className="text-[12px] text-faint py-8 text-center">Loading model catalog...</div>
      ) : groups.length === 0 ? (
        <div className="text-[12px] text-faint py-8 text-center">
          No models available. Add a provider key in Providers &amp; Keys first.
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {groups.map((g) => (
            <div key={g.provider}>
              <div className="text-[10px] uppercase tracking-wider text-faint font-semibold mb-1.5 px-1">
                {g.display}
              </div>
              <div className="flex flex-col rounded-lg border border-edge/40 overflow-hidden">
                {g.items.map((entry, i) => (
                  <button
                    key={entry.spec}
                    onClick={() => toggle(entry)}
                    disabled={busy === entry.spec}
                    className={`flex items-center justify-between px-3 py-2 text-left transition
                      ${i > 0 ? "border-t border-edge/30" : ""}
                      ${entry.enabled ? "bg-accent/5 hover:bg-accent/10" : "hover:bg-panel2/60"}
                      disabled:opacity-50`}
                  >
                    <span className="min-w-0 flex-1">
                      <span className="text-[12px] text-txt font-mono truncate block">{entry.model}</span>
                    </span>
                    <span
                      className={`shrink-0 ml-3 flex items-center justify-center w-9 h-5 rounded-full transition relative
                        ${entry.enabled ? "bg-accent/80" : "bg-edge"}`}
                    >
                      <span
                        className={`absolute w-4 h-4 rounded-full bg-white transition-transform
                          ${entry.enabled ? "translate-x-2" : "-translate-x-2"}`}
                      />
                    </span>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
