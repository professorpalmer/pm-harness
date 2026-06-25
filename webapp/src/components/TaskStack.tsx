import { useEffect, useState } from "react";
import { ChevronDown, ChevronRight, CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";
import { api, type Job } from "../lib/api";

// Task + background stack (Hermes composer/status-stack pattern): a collapsible
// strip above the composer showing the pilot's task progress and background jobs.
// Tasks here = the PM jobs this session has spawned (each swarm/implement run);
// Background = jobs still running. Fed from /api/jobs.

type Status = "pending" | "in_progress" | "completed" | "cancelled";

function jobStatus(j: Job): Status {
  const s = (j.status || "").toLowerCase();
  if (s.includes("complete") || s.includes("done")) return "completed";
  if (s.includes("fail") || s.includes("cancel") || s.includes("error")) return "cancelled";
  if (s.includes("run") || s.includes("progress") || s.includes("active")) return "in_progress";
  return "pending";
}

export default function TaskStack({ refresh }: { refresh: number }) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [openTasks, setOpenTasks] = useState(true);
  const [openBg, setOpenBg] = useState(true);

  useEffect(() => {
    const load = () => api.jobs().then(setJobs).catch(() => {});
    load();
    const t = setInterval(load, 2500);
    return () => clearInterval(t);
  }, [refresh]);

  if (jobs.length === 0) return null;

  const done = jobs.filter((j) => jobStatus(j) === "completed").length;
  const running = jobs.filter((j) => jobStatus(j) === "in_progress");

  return (
    <div className="border-t border-edge bg-panel2/60 text-[11px]">
      <Section open={openTasks} onToggle={() => setOpenTasks((v) => !v)}
        label={`Tasks ${done}/${jobs.length}`}>
        {jobs.slice().reverse().map((j) => {
          const st = jobStatus(j);
          return (
            <div key={j.id} className="flex items-center gap-2 px-4 py-1">
              <StatusIcon status={st} />
              <span className={`flex-1 truncate ${st === "completed" ? "text-muted line-through/0" : "text-txt"}`}>{j.goal}</span>
            </div>
          );
        })}
      </Section>
      {running.length > 0 && (
        <Section open={openBg} onToggle={() => setOpenBg((v) => !v)}
          label={`${running.length} Background`}>
          {running.map((j) => (
            <div key={j.id} className="flex items-center gap-2 px-4 py-1">
              <Loader2 size={11} className="animate-spin text-accent" />
              <span className="flex-1 truncate text-txt">{j.goal}</span>
            </div>
          ))}
        </Section>
      )}
    </div>
  );
}

function Section({ open, onToggle, label, children }: any) {
  return (
    <div>
      <button onClick={onToggle} className="w-full flex items-center gap-1.5 px-3 py-1.5 text-muted hover:text-txt">
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        <span className="uppercase tracking-wider text-[10px]">{label}</span>
      </button>
      {open && <div className="pb-1 max-h-40 overflow-y-auto">{children}</div>}
    </div>
  );
}

function StatusIcon({ status }: { status: Status }) {
  if (status === "completed") return <CheckCircle2 size={12} className="text-good" />;
  if (status === "in_progress") return <Loader2 size={12} className="animate-spin text-accent" />;
  if (status === "cancelled") return <XCircle size={12} className="text-risk" />;
  return <Circle size={12} className="text-muted" />;
}
