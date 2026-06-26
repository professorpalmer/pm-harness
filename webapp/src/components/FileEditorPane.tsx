import { useEffect, useRef, useState } from "react";
import { Loader2, Save, RotateCcw } from "lucide-react";
import { api } from "../lib/api";

interface FileEditorPaneProps {
  path: string;
  onClose: () => void;
  onDirtyChange: (dirty: boolean) => void;
}

export default function FileEditorPane({ path, onClose, onDirtyChange }: FileEditorPaneProps) {
  const [content, setContent] = useState("");
  const [originalContent, setOriginalContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isDirty, setIsDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const lineNumbersRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    let active = true;
    async function loadFile() {
      setLoading(true);
      setError(null);
      try {
        const res = await api.readFile(path);
        if (!active) return;
        if (res.ok) {
          setContent(res.content || "");
          setOriginalContent(res.content || "");
          setIsDirty(false);
          onDirtyChange(false);
        } else if (res.binary) {
          setError("Binary file cannot be viewed or edited in-app");
        } else {
          setError(res.error || "Failed to read file");
        }
      } catch (err: any) {
        if (active) {
          setError(err.message || "Error reading file contents");
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }
    loadFile();
    return () => {
      active = false;
    };
  }, [path]);

  const handleScroll = () => {
    if (textareaRef.current && lineNumbersRef.current) {
      lineNumbersRef.current.scrollTop = textareaRef.current.scrollTop;
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Tab") {
      e.preventDefault();
      const start = e.currentTarget.selectionStart;
      const end = e.currentTarget.selectionEnd;
      const value = e.currentTarget.value;
      const newValue = value.substring(0, start) + "  " + value.substring(end);
      setContent(newValue);
      setIsDirty(true);
      onDirtyChange(true);

      setTimeout(() => {
        if (textareaRef.current) {
          textareaRef.current.selectionStart = textareaRef.current.selectionEnd = start + 2;
        }
      }, 0);
    }
  };

  const handleSave = async () => {
    if (saving || !isDirty) return;
    setSaving(true);
    setSaveStatus("saving");
    setError(null);
    try {
      const res = await api.writeFile(path, content);
      if (res.ok) {
        setSaveStatus("saved");
        setIsDirty(false);
        onDirtyChange(false);
        setOriginalContent(content);
        // Let other components know (like workspace files tree or git view)
        window.dispatchEvent(new CustomEvent("harness-file-saved", { detail: { path } }));
        setTimeout(() => setSaveStatus("idle"), 2000);
      } else {
        setSaveStatus("error");
        setError(res.error || "Failed to save file");
      }
    } catch (err: any) {
      setSaveStatus("error");
      setError(err.message || "Error saving file");
    } finally {
      setSaving(false);
    }
  };

  const handleRevert = () => {
    if (window.confirm("Discard all local edits and restore file from disk?")) {
      setContent(originalContent);
      setIsDirty(false);
      onDirtyChange(false);
    }
  };

  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      if (mod && e.key.toLowerCase() === "s") {
        e.preventDefault();
        handleSave();
      }
    };
    window.addEventListener("keydown", handleGlobalKeyDown);
    return () => {
      window.removeEventListener("keydown", handleGlobalKeyDown);
    };
  }, [content, isDirty, saving, path, originalContent]);

  if (loading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-bg">
        <Loader2 className="animate-spin text-accent mb-2" size={24} />
        <span className="text-[12px] text-muted">Reading file...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-bg px-6 text-center">
        <span className="text-risk font-semibold text-[13px] mb-2">{error}</span>
        <button
          onClick={onClose}
          className="text-[11px] text-muted hover:text-txt underline transition-colors"
        >
          Close editor
        </button>
      </div>
    );
  }

  const lineCount = content.split("\n").length;
  const lineNumbers = Array.from({ length: Math.max(1, lineCount) }, (_, i) => i + 1).join("\n");

  return (
    <div className="flex-1 flex flex-col bg-bg h-full min-h-0 overflow-hidden relative">
      {/* Editor toolbar */}
      <div className="flex items-center justify-between px-4 py-1.5 border-b border-edge bg-panel select-none shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-[11px] font-mono text-muted truncate" title={path}>
            {path}
          </span>
          {isDirty && (
            <span className="w-2 h-2 rounded-full bg-warn shrink-0" title="Unsaved changes" />
          )}
        </div>

        <div className="flex items-center gap-3">
          {saveStatus === "saving" && (
            <span className="text-[11px] text-muted flex items-center gap-1">
              <Loader2 className="animate-spin" size={12} />
              Saving...
            </span>
          )}
          {saveStatus === "saved" && (
            <span className="text-[11px] text-good">Saved</span>
          )}
          {saveStatus === "error" && (
            <span className="text-[11px] text-risk">Save failed</span>
          )}

          <div className="flex items-center gap-1.5">
            <button
              onClick={handleRevert}
              disabled={!isDirty || saving}
              className={`flex items-center gap-1 px-2 py-1 rounded text-[11px] transition-colors border ${
                isDirty && !saving
                  ? "border-edge text-muted hover:text-txt hover:bg-panel2"
                  : "border-transparent text-faint cursor-not-allowed"
              }`}
              title="Discard unsaved changes"
            >
              <RotateCcw size={12} />
              Revert
            </button>
            <button
              onClick={handleSave}
              disabled={!isDirty || saving}
              className={`flex items-center gap-1 px-2.5 py-1 rounded text-[11px] transition-colors border ${
                isDirty && !saving
                  ? "bg-accent/15 border-accent/30 text-accent hover:bg-accent/25"
                  : "border-transparent text-faint cursor-not-allowed"
              }`}
              title="Save file (Cmd/Ctrl+S)"
            >
              <Save size={12} />
              Save
            </button>
          </div>
        </div>
      </div>

      {/* Editor area with synchronized scrolling */}
      <div className="flex-1 flex overflow-hidden relative">
        <pre
          ref={lineNumbersRef}
          className="w-12 bg-panel/10 text-right pr-2.5 select-none text-muted/50 py-3 overflow-hidden font-mono text-[13px] leading-relaxed border-r border-edge/30 select-none pointer-events-none"
          style={{ margin: 0 }}
        >
          {lineNumbers}
        </pre>
        <textarea
          ref={textareaRef}
          value={content}
          onChange={(e) => {
            setContent(e.target.value);
            setIsDirty(true);
            onDirtyChange(true);
          }}
          onScroll={handleScroll}
          onKeyDown={handleKeyDown}
          className="flex-1 bg-transparent text-txt resize-none outline-none border-none p-3 overflow-auto font-mono text-[13px] leading-relaxed whitespace-pre focus:ring-0"
          style={{ tabSize: 2 }}
          placeholder="Write code here..."
          spellCheck={false}
        />
      </div>
    </div>
  );
}
