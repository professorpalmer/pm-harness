import { useEffect, useRef, useState } from "react";
import { RotateCw, ExternalLink, ArrowLeft, ArrowRight } from "lucide-react";

// In-app browser pane. Design adapted from professorpalmer\'s Hermes fork branch
// feat/desktop-browser-panel (BrowserState shape, nav toolbar + editable address
// bar, nonce reload). Web build uses an iframe; a future Electron build swaps to
// a <webview> behind the transport seam with the same chrome.
const DEFAULT_URL = "https://duckduckgo.com";

export default function BrowserPane() {
  const [url, setUrl] = useState(DEFAULT_URL);
  const [draft, setDraft] = useState(DEFAULT_URL);
  const [editing, setEditing] = useState(false);
  const [nonce, setNonce] = useState(0);
  const [loading, setLoading] = useState(false);
  const [canBack, setCanBack] = useState(false);
  const [canFwd, setCanFwd] = useState(false);
  const frameRef = useRef<HTMLIFrameElement | null>(null);
  const webviewRef = useRef<any>(null);
  const isDesktop = !!(window as any).harnessIPC;

  useEffect(() => { if (!editing) setDraft(url); }, [editing, url]);

  const normalize = (raw: string): string => {
    const v = raw.trim();
    if (!v) return url;
    if (/^https?:\/\//i.test(v)) return v;
    if (/^[\w-]+(\.[\w-]+)+/.test(v)) return "https://" + v;  // looks like a domain
    return "https://duckduckgo.com/?q=" + encodeURIComponent(v); // else search
  };

  const go = (raw: string) => {
    const next = normalize(raw);
    setUrl(next); setLoading(true);
    if (isDesktop && webviewRef.current) { try { webviewRef.current.loadURL(next); } catch {} }
    else setNonce((n) => n + 1);
  };
  const reload = () => {
    setLoading(true);
    if (isDesktop && webviewRef.current) { try { webviewRef.current.reload(); } catch {} }
    else setNonce((n) => n + 1);
  };
  const back = () => { if (webviewRef.current?.canGoBack?.()) webviewRef.current.goBack(); };
  const fwd = () => { if (webviewRef.current?.canGoForward?.()) webviewRef.current.goForward(); };

  // Attach webview nav listeners (desktop only). The <webview> is created by the
  // renderer below; we wire load + url events to update chrome state.
  useEffect(() => {
    if (!isDesktop) return;
    const wv: any = webviewRef.current;
    if (!wv) return;
    const onStart = () => setLoading(true);
    const onStop = () => {
      setLoading(false);
      try {
        setCanBack(wv.canGoBack()); setCanFwd(wv.canGoForward());
        const u = wv.getURL(); if (u && !editing) { setUrl(u); setDraft(u); }
      } catch {}
    };
    wv.addEventListener("did-start-loading", onStart);
    wv.addEventListener("did-stop-loading", onStop);
    return () => {
      wv.removeEventListener("did-start-loading", onStart);
      wv.removeEventListener("did-stop-loading", onStop);
    };
  }, [isDesktop, editing]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-1 px-2 py-1.5 border-b border-edge">
        {isDesktop && <NavBtn label="Back" onClick={back} disabled={!canBack}><ArrowLeft size={12} /></NavBtn>}
        {isDesktop && <NavBtn label="Forward" onClick={fwd} disabled={!canFwd}><ArrowRight size={12} /></NavBtn>}
        <NavBtn label="Reload" onClick={reload}><RotateCw size={12} className={loading ? "animate-spin" : ""} /></NavBtn>
        <form onSubmit={(e) => { e.preventDefault(); setEditing(false); go(draft); }} className="flex-1">
          <input value={draft} onChange={(e) => setDraft(e.target.value)}
            onFocus={() => setEditing(true)} onBlur={() => setEditing(false)}
            spellCheck={false}
            className="w-full bg-bg border border-edge rounded-md px-2 h-6 text-[11px] text-txt
                       focus:outline-none focus:border-accent2" />
        </form>
        <NavBtn label="Open externally" onClick={() => window.open(url, "_blank")}><ExternalLink size={12} /></NavBtn>
      </div>
      <div className="flex-1 relative bg-white">
        {isDesktop ? (
          // Real browser: Electron <webview> bypasses X-Frame-Options/CSP. Created
          // via dangerouslySetInnerHTML so React does not re-mount it per render
          // (which would lose its navigation methods + history).
          <webview
            ref={webviewRef as any}
            src={DEFAULT_URL}
            // @ts-expect-error -- webview is an Electron element, not in React JSX types
            allowpopups="true"
            className="absolute inset-0 w-full h-full border-0"
            style={{ display: "flex" }}
          />
        ) : (
          <>
            <iframe ref={frameRef} key={nonce} src={url} title="browser"
              onLoad={() => setLoading(false)}
              className="absolute inset-0 w-full h-full border-0"
              sandbox="allow-scripts allow-same-origin allow-forms allow-popups" />
            <div className="absolute bottom-0 inset-x-0 bg-panel/95 border-t border-edge px-3 py-1.5
                            text-[10px] text-muted">
              Web preview: many sites block embedding (X-Frame-Options/CSP). Full
              navigation arrives in the desktop build via the webview.
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function NavBtn({ label, onClick, children }: any) {
  return (
    <button title={label} onClick={onClick} type="button"
      className="grid place-items-center size-6 shrink-0 rounded-md text-muted hover:text-txt hover:bg-panel2 transition">
      {children}
    </button>
  );
}
