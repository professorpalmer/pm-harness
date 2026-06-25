import { useEffect, useRef } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";
import { postJSON, stream, withToken } from "../lib/transport";

// Built-in terminal: xterm.js front-end over the harness PTY backend.
// create -> SSE stream output (base64 frames) -> POST keystrokes -> resize -> kill.
export default function TerminalPane() {
  const hostRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);
  const idRef = useRef<string>("");
  const cancelRef = useRef<null | (() => void)>(null);

  useEffect(() => {
    if (!hostRef.current) return;
    const term = new Terminal({
      fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
      fontSize: 12,
      theme: {
        background: "#0a0a0c",
        foreground: "#d4d4d8",
        cursor: "#7c8cff",
        selectionBackground: "#2a2a3a",
      },
      cursorBlink: true,
      scrollback: 5000,
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(hostRef.current);
    try { fit.fit(); } catch { /* ignore */ }
    termRef.current = term;

    let disposed = false;

    (async () => {
      try {
        const res = await postJSON<{ id: string }>("/api/terminal/create", {
          cols: term.cols, rows: term.rows,
        });
        if (disposed) { postJSON("/api/terminal/kill", { id: res.id }); return; }
        idRef.current = res.id;

        // keystrokes -> backend
        term.onData((data) => {
          if (idRef.current) postJSON("/api/terminal/write", { id: idRef.current, data });
        });
        // resize -> backend
        term.onResize(({ cols, rows }) => {
          if (idRef.current) postJSON("/api/terminal/resize", { id: idRef.current, cols, rows });
        });

        // stream output
        cancelRef.current = stream(
          `/api/terminal/stream?id=${res.id}`,
          (ev: any) => {
            if (ev.kind === "data" && ev.b64) {
              try { term.write(_b64ToBytes(ev.b64)); } catch { /* ignore */ }
            } else if (ev.kind === "exit") {
              term.write("\r\n\x1b[90m[process exited]\x1b[0m\r\n");
            }
          },
          undefined,
          () => { /* stream error -- backend gone */ }
        );
      } catch (e) {
        term.write("\r\n\x1b[31mFailed to start terminal.\x1b[0m\r\n");
      }
    })();

    // fit on container resize
    const ro = new ResizeObserver(() => { try { fit.fit(); } catch { /* ignore */ } });
    ro.observe(hostRef.current);

    return () => {
      disposed = true;
      ro.disconnect();
      if (cancelRef.current) cancelRef.current();
      if (idRef.current) postJSON("/api/terminal/kill", { id: idRef.current });
      term.dispose();
    };
  }, []);

  return (
    <div className="h-full flex flex-col bg-[#0a0a0c]">
      <div className="px-3 py-2 border-b border-edge text-[10px] uppercase tracking-wider text-faint font-medium shrink-0">
        Terminal
      </div>
      <div ref={hostRef} className="flex-1 min-h-0 p-1.5 overflow-hidden" />
    </div>
  );
}

// decode a base64 string to a Uint8Array for xterm.write (preserves raw bytes/ANSI)
function _b64ToBytes(b64: string): Uint8Array {
  const bin = atob(b64);
  const arr = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
  return arr;
}

void withToken;
