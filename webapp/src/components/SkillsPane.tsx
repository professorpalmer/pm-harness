import { useEffect, useState } from "react";
import { GraduationCap, Check, X, Archive, Sparkles } from "lucide-react";
import { api } from "../lib/api";

// Self-learning panel: review AUTO-DISTILLED candidate skills (PENDING) and
// approve/reject. Approved skills load into the pilot's context next session.
// The human gate is the point -- a bad auto-skill is worse than none.
export default function SkillsPane() {
  const [skills, setSkills] = useState<any[]>([]);
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");
  const [expanded, setExpanded] = useState<string>("");

  const refresh = () => api.skills().then(setSkills).catch(() => {});
  useEffect(() => { refresh(); const t = setInterval(refresh, 5000); return () => clearInterval(t); }, []);

  const distill = async () => {
    setBusy("distill"); setMsg("");
    try {
      const r = await api.skillDistill();
      setMsg(r.status === "proposed" ? `Proposed: ${r.name}`
        : r.status === "duplicate" ? "Skipped: similar skill exists"
        : `Skipped: ${r.reason || r.status}`);
      await refresh();
    } finally { setBusy(""); }
  };
  const approve = async (slug: string) => { setBusy(slug); try { await api.skillApprove(slug); await refresh(); } finally { setBusy(""); } };
  const reject = async (slug: string) => { setBusy(slug); try { await api.skillReject(slug); await refresh(); } finally { setBusy(""); } };

  const pending = skills.filter((s) => s.state === "pending");
  const active = skills.filter((s) => s.state === "active");

  return (
    <div className="flex flex-col h-full text-[12px]">
      <div className="flex items-center justify-between px-3 py-2 border-b border-edge">
        <span className="uppercase tracking-wider text-[10px] text-faint font-medium flex items-center gap-1.5">
          <GraduationCap size={11} /> Skills
        </span>
        <button onClick={distill} disabled={busy === "distill"}
          className="text-[10px] flex items-center gap-1 px-1.5 h-5 rounded bg-accent2 text-accent hover:brightness-125 disabled:opacity-40">
          <Sparkles size={10} /> Distill session
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-2 flex flex-col gap-2">
        {msg && <div className="text-[10px] text-muted px-1">{msg}</div>}

        {pending.length > 0 && (
          <div>
            <div className="uppercase tracking-wider text-[10px] text-warn mb-1 px-1">Pending review ({pending.length})</div>
            {pending.map((s) => (
              <div key={s.slug} className="border border-warn/30 rounded-lg p-2 bg-warn/5 mb-1.5">
                <div className="font-medium text-txt">{s.name}</div>
                <div className="text-faint text-[10px] mt-0.5">{s.description}</div>
                <button onClick={() => setExpanded(expanded === s.slug ? "" : s.slug)}
                  className="text-accent text-[10px] mt-1">{expanded === s.slug ? "hide" : "view steps"}</button>
                {expanded === s.slug && <pre className="text-[10px] text-muted whitespace-pre-wrap mt-1 font-mono">{s.body}</pre>}
                <div className="flex gap-1.5 mt-2">
                  <button onClick={() => approve(s.slug)} disabled={busy === s.slug}
                    className="flex-1 h-6 rounded bg-good/20 text-good text-[10px] font-medium flex items-center justify-center gap-1"><Check size={11} /> Approve</button>
                  <button onClick={() => reject(s.slug)} disabled={busy === s.slug}
                    className="flex-1 h-6 rounded bg-risk/15 text-risk text-[10px] font-medium flex items-center justify-center gap-1"><X size={11} /> Reject</button>
                </div>
              </div>
            ))}
          </div>
        )}

        <div>
          <div className="uppercase tracking-wider text-[10px] text-faint mb-1 px-1">Active ({active.length})</div>
          {active.length === 0 && <div className="text-faint text-[10px] px-1">No active skills yet. Distill a finished session to propose one.</div>}
          {active.map((s) => (
            <div key={s.slug} className="border border-edge rounded-lg p-2 bg-panel2/40 mb-1.5">
              <div className="flex items-center gap-2">
                <span className="font-medium text-txt flex-1 truncate">{s.name}</span>
                <span className="text-faint text-[10px]">used {s.used_count}x</span>
                <button onClick={() => reject(s.slug)} title="Archive" className="text-muted hover:text-risk"><Archive size={11} /></button>
              </div>
              <div className="text-faint text-[10px] mt-0.5">{s.description}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
