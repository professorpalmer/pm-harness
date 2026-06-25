import { useCallback, useRef } from "react";

// A 4px draggable divider. side="left" means it resizes the pane to its LEFT
// (delta = mouse dx); side="right" means the pane to its RIGHT (delta = -dx).
export default function Resizer({ onResize, side = "left" }: {
  onResize: (deltaPx: number) => void;
  side?: "left" | "right";
}) {
  const startX = useRef(0);
  const onDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    startX.current = e.clientX;
    const move = (ev: MouseEvent) => {
      const dx = ev.clientX - startX.current;
      startX.current = ev.clientX;
      onResize(side === "left" ? dx : -dx);
    };
    const up = () => {
      document.removeEventListener("mousemove", move);
      document.removeEventListener("mouseup", up);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    document.addEventListener("mousemove", move);
    document.addEventListener("mouseup", up);
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, [onResize, side]);

  return (
    <div onMouseDown={onDown}
      className="w-1 shrink-0 cursor-col-resize bg-transparent hover:bg-accent2/60 transition-colors"
      style={{ marginLeft: -2, marginRight: -2, zIndex: 10 }} />
  );
}
