import { useEffect, useState } from "react";
import { Loader2, CheckCircle2, XCircle, Circle, ChevronDown, ChevronRight, Cpu, Activity, Network } from "lucide-react";
import { api, type SwarmLive, type Job, type Artifact } from "../lib/api";

function jobStatus(j: Job): "pending" | "in_progress" | "completed" | "cancelled" {
  const s = (j.status || "").toLowerCase();
  if (s.includes("complete") || s.includes("done")) return "completed";
  if (s.includes("fail") || s.includes("cancel") || s.includes("error")) return "cancelled";
  if (s.includes("run") || s.includes("progress") || s.includes("active")) return "in_progress";
  return "pending";
}

export default function SwarmPane() {
  const [data, setData] = useState<SwarmLive | null>(null);
  const [pollInterval, setPollInterval] = useState(2000);
  const [expandedJobs, setExpandedJobs] = useState<Record<string, boolean>>({});
  const [expandedAlts, setExpandedAlts] = useState<Record<string, boolean>>({});

  useEffect(() => {
    let active = true;
    const fetchSwarm = () => {
      api.swarmLive()
        .then((res) => {
          if (!active) return;
          setData(res);
          // if any job is active/running, poll faster (2s); else slower (5s)
          const hasRunning = (res.jobs || []).some((j) => {
            const st = jobStatus(j);
            return st === "in_progress";
          });
          const nextInterval = hasRunning ? 2000 : 5000;
          if (nextInterval !== pollInterval) {
            setPollInterval(nextInterval);
          }
        })
        .catch((err) => {
          console.error("Swarm Live polling error:", err);
        });
    };

    fetchSwarm();
    const intervalId = setInterval(fetchSwarm, pollInterval);
    return () => {
      active = false;
      clearInterval(intervalId);
    };
  }, [pollInterval]);

  const jobs = data?.jobs || [];
  const anyRunning = jobs.some((j) => jobStatus(j) === "in_progress");

  return (
    <div className="flex flex-col h-full overflow-hidden bg-panel">
      {jobs.length > 0 && (
        <div className="shrink-0 flex items-center justify-between px-3 py-2 border-b border-edge/60 select-none">
          <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-faint font-semibold">
            <Network size={11} className="text-faint/70" />
            <span>Swarm Jobs</span>
            <span className="text-faint/60 normal-case tracking-normal">({jobs.length})</span>
          </div>
          {anyRunning && (
            <span className="flex items-center gap-1 text-[10px] text-accent">
              <Loader2 size={10} className="animate-spin" /> running
            </span>
          )}
        </div>
      )}
      {/* Scrollable Jobs list */}
      <div className="flex-1 overflow-y-auto p-2 flex flex-col gap-2">
        {jobs.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-center px-6 gap-2">
            <Network size={20} className="text-faint/50" />
            <span className="text-[12px] text-muted font-medium">No swarm jobs yet</span>
            <span className="text-[10.5px] text-faint leading-relaxed">
              Puppetmaster jobs dispatched via run_implement, run_parallel, or
              run_swarm appear here with their router choice, workers, and live
              artifacts. Inline tool calls show in the chat transcript instead.
            </span>
          </div>
        ) : (
          jobs.slice().reverse().map((j) => {
            const st = jobStatus(j);
            const manualExpanded = expandedJobs[j.id];
            // default to expanded if it is running and has not been explicitly collapsed
            const isExpanded = manualExpanded !== undefined ? manualExpanded : (st === "in_progress");

            const routingArts = (j.artifacts || []).filter(
              (a: Artifact) => a.type.toUpperCase() === "ROUTING"
            );
            const streamArts = (j.artifacts || []).filter(
              (a: Artifact) => a.type.toUpperCase() !== "ROUTING"
            );

            return (
              <div
                key={j.id}
                className="rounded border border-edge bg-panel2/30 flex flex-col overflow-hidden transition-colors"
              >
                {/* Header Row */}
                <button
                  onClick={() =>
                    setExpandedJobs((prev) => ({ ...prev, [j.id]: !isExpanded }))
                  }
                  className="w-full flex items-center justify-between p-2 hover:bg-panel2/50 text-left transition-colors select-none focus:outline-none border-b border-edge/30"
                >
                  <div className="flex items-center gap-2 min-w-0 flex-1">
                    <span className="shrink-0 text-faint">
                      {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                    </span>
                    <span className="shrink-0">
                      {st === "in_progress" ? (
                        <Loader2 size={12} className="animate-spin text-accent" />
                      ) : st === "completed" ? (
                        <CheckCircle2 size={12} className="text-good" />
                      ) : st === "cancelled" ? (
                        <XCircle size={12} className="text-risk" />
                      ) : (
                        <Circle size={12} className="text-muted" />
                      )}
                    </span>
                    <span className="font-semibold text-[11px] text-txt truncate" title={j.goal}>
                      {j.goal}
                    </span>
                  </div>

                  <div className="flex items-center gap-3 shrink-0 text-[10px] pl-2">
                    {j.est_cost_usd !== undefined && j.est_cost_usd > 0 && (
                      <span className="font-mono text-good">
                        ${Number(j.est_cost_usd).toFixed(5)}
                      </span>
                    )}
                    {j.tokens !== undefined && j.tokens > 0 && (
                      <span className="text-muted font-mono">
                        {j.tokens.toLocaleString()} t
                      </span>
                    )}
                  </div>
                </button>

                {/* Expanded details */}
                {isExpanded && (
                  <div className="p-2 flex flex-col gap-2 bg-panel2/10">
                    {/* Routing Details */}
                    {routingArts.length > 0 && (
                      <div className="flex flex-col gap-1.5">
                        {routingArts.map((art: Artifact, idx: number) => {
                          const hasRejected = art.rejected && art.rejected.length > 0;
                          const key = `${art.id || idx}`;
                          const altsExpanded = !!expandedAlts[key];

                          return (
                            <div
                              key={key}
                              className="p-2 bg-panel rounded border border-edge/45 text-[10px] flex flex-col gap-1"
                            >
                              <div className="flex items-center justify-between text-muted">
                                <span className="flex items-center gap-1 truncate max-w-[70%]">
                                  <Cpu size={11} className="text-accent shrink-0" />
                                  <span>Router choice:</span>
                                  <span className="text-txt font-mono font-medium truncate" title={art.model}>
                                    {art.model || "Unknown model"}
                                  </span>
                                </span>
                                {art.est_cost_usd !== undefined && art.est_cost_usd > 0 && (
                                  <span className="font-mono text-good shrink-0 font-semibold">
                                    ${Number(art.est_cost_usd).toFixed(5)}
                                  </span>
                                )}
                              </div>

                              {art.detail && (
                                <div className="text-[9.5px] text-faint bg-panel2/20 p-1.5 rounded border border-edge/20 whitespace-pre-wrap leading-relaxed mt-1">
                                  {art.detail}
                                </div>
                              )}

                              {hasRejected && (
                                <div className="mt-1 border-t border-edge/20 pt-1">
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setExpandedAlts((prev) => ({ ...prev, [key]: !altsExpanded }));
                                    }}
                                    className="text-[9px] text-accent hover:underline flex items-center gap-0.5 focus:outline-none"
                                  >
                                    {altsExpanded ? "Hide rejected models" : "Show rejected models"}
                                  </button>
                                  {altsExpanded && (
                                    <div className="mt-1.5 flex flex-col gap-1 pl-2 border-l border-edge/40">
                                      {art.rejected?.map((rej: any, ridx: number) => (
                                        <div key={ridx} className="text-[9px] text-faint">
                                          <span className="font-mono text-muted">{rej.model}</span>: {rej.reason}
                                        </div>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}

                    {/* Workers / Tasks */}
                    {j.tasks && j.tasks.length > 0 && (
                      <div className="border-t border-edge/20 pt-1.5">
                        <div className="text-[9px] uppercase tracking-wider text-faint font-medium mb-1">
                          Workers ({j.tasks.length})
                        </div>
                        <div className="flex flex-col gap-1">
                          {j.tasks.map((task) => {
                            const tst = task.status.toLowerCase();
                            const isRunning = tst.includes("run") || tst.includes("progress") || tst.includes("active");
                            const isComplete = tst.includes("complete") || tst.includes("done");
                            const isFail = tst.includes("fail") || tst.includes("cancel") || tst.includes("error");

                            return (
                              <div
                                key={task.id}
                                className="p-1.5 rounded bg-panel/25 border border-edge/20 flex items-start gap-2 text-[10px]"
                              >
                                <span className="mt-0.5 shrink-0">
                                  {isRunning ? (
                                    <Loader2 size={10} className="animate-spin text-accent" />
                                  ) : isComplete ? (
                                    <CheckCircle2 size={10} className="text-good" />
                                  ) : isFail ? (
                                    <XCircle size={10} className="text-risk" />
                                  ) : (
                                    <Circle size={10} className="text-muted" />
                                  )}
                                </span>
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center justify-between">
                                    <span className="font-semibold text-txt truncate">
                                      {task.role || "Worker"}{" "}
                                      <span className="text-faint font-normal">
                                        ({task.adapter || "no-adapter"})
                                      </span>
                                    </span>
                                    <span
                                      className={`text-[8px] uppercase font-bold px-1 rounded ${
                                        isRunning
                                          ? "text-accent bg-accent/10"
                                          : isComplete
                                          ? "text-good bg-good/10"
                                          : isFail
                                          ? "text-risk bg-risk/10"
                                          : "text-muted bg-panel"
                                      }`}
                                    >
                                      {task.status}
                                    </span>
                                  </div>
                                  {task.instruction && (
                                    <div
                                      className="text-muted text-[9.5px] mt-0.5 truncate"
                                      title={task.instruction}
                                    >
                                      {task.instruction}
                                    </div>
                                  )}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* Artifacts Stream */}
                    {streamArts.length > 0 && (
                      <div className="border-t border-edge/20 pt-1.5 flex flex-col">
                        <div className="text-[9px] uppercase tracking-wider text-faint font-medium mb-1">
                          Artifacts Stream
                        </div>
                        <div className="max-h-36 overflow-y-auto pr-1 flex flex-col gap-1 border border-edge/20 rounded p-1.5 bg-panel/30">
                          {streamArts.map((art: Artifact, idx: number) => (
                            <div
                              key={art.id || idx}
                              className="text-[9.5px] border-b border-edge/10 pb-1 last:border-0 last:pb-0 flex flex-col gap-0.5"
                            >
                              <div className="flex items-center justify-between">
                                <span className="font-bold text-accent uppercase tracking-wider text-[8px]">
                                  {art.type}
                                </span>
                                {art.confidence !== undefined && art.confidence !== null && (
                                  <span className="text-[8px] text-faint bg-edge/20 px-1 rounded">
                                    Conf: {Math.round(art.confidence * 100)}%
                                  </span>
                                )}
                              </div>
                              <div className="text-txt break-words leading-relaxed">
                                {art.headline}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Footer: session totals. Labeled "SWARM RUNNING" only when a job is
          actually in flight; otherwise it's clearly session-cumulative totals,
          not a false "active" indicator. */}
      {data?.session && (
        <div className="shrink-0 border-t border-edge bg-panel2/80 px-3 py-2 flex items-center justify-between text-[10px] text-muted font-medium select-none">
          <div className="flex items-center gap-1.5 min-w-0">
            {anyRunning ? (
              <>
                <Loader2 size={11} className="text-accent shrink-0 animate-spin" />
                <span className="truncate">
                  SWARM RUNNING: <span className="text-txt font-mono font-semibold">{data.session.driver || "unknown"}</span>
                </span>
              </>
            ) : (
              <>
                <Activity size={11} className="text-faint shrink-0" />
                <span className="truncate text-faint">
                  Session total <span className="text-muted font-mono">{data.session.driver || ""}</span>
                </span>
              </>
            )}
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <span>
              Cost: <strong className="text-good font-mono font-semibold">${Number(data.session.est_cost_usd).toFixed(5)}</strong>
            </span>
            <span>
              Tokens: <strong className="text-txt font-mono font-semibold">{data.session.tokens_used.toLocaleString()}</strong>
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
