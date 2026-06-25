import { useEffect, useState, useRef } from "react";
import { Network, RefreshCw, BookOpen, AlertTriangle } from "lucide-react";
import { api, type WikiGraphData } from "../lib/api";

interface NodeSim {
  id: string;
  title: string;
  section?: string;
  tags?: string[];
  x: number;
  y: number;
  vx: number;
  vy: number;
}

export default function WikiGraphPane() {
  const [data, setData] = useState<WikiGraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [renderNodes, setRenderNodes] = useState<NodeSim[]>([]);
  const [hoveredNode, setHoveredNode] = useState<NodeSim | null>(null);
  const [selectedNode, setSelectedNode] = useState<NodeSim | null>(null);
  const [, setDraggedNodeId] = useState<string | null>(null);

  const svgRef = useRef<SVGSVGElement | null>(null);
  const simNodesRef = useRef<NodeSim[]>([]);
  const draggedNodeIdRef = useRef<string | null>(null);
  const [dimensions, setDimensions] = useState({ width: 400, height: 400 });
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Measure container dimensions
  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        setDimensions({
          width: Math.max(width, 250),
          height: Math.max(height - 120, 250), // reserve space for headers/tooltips
        });
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getWikiGraph();
      setData(res);
      if (res.status === "error") {
        setError(res.error || "Wiki unreachable");
      }
    } catch (err: any) {
      setError(err?.message || "Failed to fetch wiki graph");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // Initialize simulation nodes when data changes
  useEffect(() => {
    if (!data || data.nodes.length === 0) {
      simNodesRef.current = [];
      setRenderNodes([]);
      return;
    }

    const { width, height } = dimensions;
    const existingMap = new Map(simNodesRef.current.map(n => [n.id, n]));

    // Initialize/re-use coordinates
    const nextNodes: NodeSim[] = data.nodes.map((n, i) => {
      const existing = existingMap.get(n.id);
      if (existing) {
        return {
          ...existing,
          title: n.title,
          section: n.section,
          tags: n.tags,
        };
      }
      // Spread in circular layout
      const angle = (i / data.nodes.length) * 2 * Math.PI;
      const r = Math.min(width, height) * 0.25 * Math.random();
      return {
        id: n.id,
        title: n.title,
        section: n.section,
        tags: n.tags,
        x: width / 2 + Math.cos(angle) * r,
        y: height / 2 + Math.sin(angle) * r,
        vx: 0,
        vy: 0,
      };
    });

    simNodesRef.current = nextNodes;
    setRenderNodes([...nextNodes]);
  }, [data, dimensions.width, dimensions.height]);

  // Simulation tick loop
  useEffect(() => {
    if (loading || !data || data.nodes.length === 0) return;

    let animFrame: number;

    const tick = () => {
      const simNodes = simNodesRef.current;
      const n = simNodes.length;
      if (n === 0) return;

      const w = dimensions.width;
      const h = dimensions.height;
      const cx = w / 2;
      const cy = h / 2;

      // 1. Repulsion between all nodes
      const repelStrength = 180;
      for (let i = 0; i < n; i++) {
        const a = simNodes[i];
        for (let j = i + 1; j < n; j++) {
          const b = simNodes[j];
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const distSq = dx * dx + dy * dy;
          const dist = Math.sqrt(distSq) || 1;
          if (dist < 200) {
            const force = repelStrength / (distSq + 12);
            a.vx -= (dx / dist) * force;
            a.vy -= (dy / dist) * force;
            b.vx += (dx / dist) * force;
            b.vy += (dy / dist) * force;
          }
        }
      }

      // 2. Attraction along edges
      const linkDistance = 70;
      const attractStrength = 0.04;
      const edges = data.edges || [];
      for (const edge of edges) {
        const a = simNodes.find(node => node.id === edge.source);
        const b = simNodes.find(node => node.id === edge.target);
        if (a && b) {
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          const force = (dist - linkDistance) * attractStrength;
          a.vx += (dx / dist) * force;
          a.vy += (dy / dist) * force;
          b.vx -= (dx / dist) * force;
          b.vy -= (dy / dist) * force;
        }
      }

      // 3. Gravity/boundaries and movement integration
      const gravity = 0.025;
      for (let i = 0; i < n; i++) {
        const a = simNodes[i];
        if (a.id === draggedNodeIdRef.current) continue; // let drag override physics

        // center gravity pull
        a.vx += (cx - a.x) * gravity;
        a.vy += (cy - a.y) * gravity;

        // friction
        const friction = 0.82;
        a.vx *= friction;
        a.vy *= friction;

        a.x += a.vx;
        a.y += a.vy;

        // bound clamping
        const rPad = 12;
        if (a.x < rPad) { a.x = rPad; a.vx = 0; }
        if (a.x > w - rPad) { a.x = w - rPad; a.vx = 0; }
        if (a.y < rPad) { a.y = rPad; a.vy = 0; }
        if (a.y > h - rPad) { a.y = h - rPad; a.vy = 0; }
      }

      setRenderNodes([...simNodes]);
      animFrame = requestAnimationFrame(tick);
    };

    animFrame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animFrame);
  }, [data, loading, dimensions.width, dimensions.height]);

  const handleMouseDown = (e: React.MouseEvent<any>, nodeId: string) => {
    e.preventDefault();
    draggedNodeIdRef.current = nodeId;
    setDraggedNodeId(nodeId);
  };

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!draggedNodeIdRef.current || !svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const node = simNodesRef.current.find(n => n.id === draggedNodeIdRef.current);
    if (node) {
      node.x = x;
      node.y = y;
      node.vx = 0;
      node.vy = 0;
      // Instant visual update for drag responsiveness
      setRenderNodes([...simNodesRef.current]);
    }
  };

  const handleMouseUp = () => {
    draggedNodeIdRef.current = null;
    setDraggedNodeId(null);
  };

  // Dragging support: window-level mouseup fallback
  useEffect(() => {
    const onGlobalMouseUp = () => {
      if (draggedNodeIdRef.current) {
        draggedNodeIdRef.current = null;
        setDraggedNodeId(null);
      }
    };
    window.addEventListener("mouseup", onGlobalMouseUp);
    return () => window.removeEventListener("mouseup", onGlobalMouseUp);
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-2 text-muted">
        <RefreshCw size={18} className="animate-spin text-accent" />
        <span className="text-[11px] uppercase tracking-wider font-medium">Loading wiki graph...</span>
      </div>
    );
  }

  // Not configured fallback
  if (!data || data.status === "not_configured" || !data.configured) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-6 text-center gap-4">
        <div className="p-3 bg-edge/30 rounded-full border border-edge">
          <Network size={22} className="text-faint" />
        </div>
        <div className="flex flex-col gap-1.5 max-w-[280px]">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-txt">Wiki Not Configured</h3>
          <p className="text-[11px] text-muted leading-relaxed">
            Set <code className="px-1 py-0.5 bg-panel2 border border-edge rounded text-accent font-mono text-[10px]">HARNESS_WIKI_URL</code> in your environment or configuration to visualize your portable-llm-wiki page graph.
          </p>
        </div>
        <button
          onClick={fetchData}
          className="flex items-center gap-1.5 text-[10px] font-semibold text-accent hover:text-accent2 bg-accent2/10 hover:bg-accent2/20 border border-accent/20 px-3 py-1.5 rounded transition-colors"
        >
          <RefreshCw size={11} />
          RETRY
        </button>
      </div>
    );
  }

  // Error/Unreachable fallback
  if (error || data.status === "error") {
    return (
      <div className="flex flex-col items-center justify-center h-full p-6 text-center gap-4">
        <div className="p-3 bg-risk/10 rounded-full border border-risk/20">
          <AlertTriangle size={22} className="text-risk" />
        </div>
        <div className="flex flex-col gap-1.5 max-w-[280px]">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-risk">Wiki Unreachable</h3>
          <p className="text-[11px] text-muted leading-relaxed">
            Could not connect to the wiki server. Make sure it is running at:
            <br />
            <span className="font-mono text-[10px] text-txt select-all">{data.base_url || "the configured URL"}</span>
          </p>
          {error && (
            <p className="text-[9px] text-faint bg-panel2 p-1.5 border border-edge/30 rounded font-mono break-all leading-normal max-h-24 overflow-y-auto">
              {error}
            </p>
          )}
        </div>
        <button
          onClick={fetchData}
          className="flex items-center gap-1.5 text-[10px] font-semibold text-accent hover:text-accent2 bg-accent2/10 hover:bg-accent2/20 border border-accent/20 px-3 py-1.5 rounded transition-colors"
        >
          <RefreshCw size={11} />
          RETRY CONNECTION
        </button>
      </div>
    );
  }

  if (renderNodes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-6 text-center gap-2">
        <BookOpen size={20} className="text-faint" />
        <h3 className="text-xs font-semibold text-txt uppercase tracking-wider">Empty Wiki</h3>
        <p className="text-[11px] text-muted">Ingest your first page to populate this graph.</p>
        <button
          onClick={fetchData}
          className="mt-2 flex items-center gap-1.5 text-[10px] font-semibold text-accent border border-accent/20 px-2.5 py-1 rounded hover:bg-accent2/10 transition-colors"
        >
          <RefreshCw size={11} />
          REFRESH
        </button>
      </div>
    );
  }

  // Select / Hover relationship mapping
  const activeNode = selectedNode || hoveredNode;
  const activeNeighbors = new Set<string>();
  if (activeNode) {
    activeNeighbors.add(activeNode.id);
    (data.edges || []).forEach(e => {
      if (e.source === activeNode.id) activeNeighbors.add(edgeTargetSlug(e.target));
      if (edgeTargetSlug(e.target) === activeNode.id) activeNeighbors.add(e.source);
    });
  }

  function edgeTargetSlug(target: string): string {
    return target.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  }

  return (
    <div ref={containerRef} className="flex flex-col h-full overflow-hidden select-none bg-panel">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-edge py-2 px-3 bg-panel2/30">
        <div className="flex items-center gap-1.5">
          <Network size={12} className="text-accent" />
          <span className="text-[10px] font-bold uppercase tracking-wider text-txt">Wiki Graph</span>
          <span className="text-[9px] text-faint px-1 bg-edge/40 rounded-full border border-edge font-normal font-mono">
            {renderNodes.length}
          </span>
        </div>
        <button
          onClick={fetchData}
          title="Refresh Graph"
          className="text-faint hover:text-txt p-1 rounded hover:bg-edge/45 transition-colors"
        >
          <RefreshCw size={10} />
        </button>
      </div>

      {/* SVG Canvas */}
      <div className="flex-1 relative overflow-hidden bg-panel/30">
        <svg
          ref={svgRef}
          width={dimensions.width}
          height={dimensions.height}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          className="block w-full h-full touch-none"
        >
          {/* Arrow definitions for links */}
          <defs>
            <marker
              id="arrow"
              viewBox="0 0 10 10"
              refX="18"
              refY="5"
              markerWidth="5"
              markerHeight="5"
              orient="auto-start-reverse"
            >
              <path d="M 0 1 L 10 5 L 0 9 z" fill="#1f1f25" className="opacity-40" />
            </marker>
            <marker
              id="arrow-active"
              viewBox="0 0 10 10"
              refX="18"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 1 L 10 5 L 0 9 z" fill="#7c93ff" />
            </marker>
          </defs>

          {/* Links (Edges) */}
          <g>
            {(data.edges || []).map((edge, i) => {
              const srcNode = renderNodes.find(n => n.id === edge.source);
              // Support matching slugs defensively
              const tgtNode = renderNodes.find(n => n.id === edgeTargetSlug(edge.target));
              if (!srcNode || !tgtNode) return null;

              const isEdgeActive = activeNode && (srcNode.id === activeNode.id || tgtNode.id === activeNode.id);
              const isDimmed = activeNode && !isEdgeActive;

              return (
                <line
                  key={`edge-${i}`}
                  x1={srcNode.x}
                  y1={srcNode.y}
                  x2={tgtNode.x}
                  y2={tgtNode.y}
                  markerEnd={isEdgeActive ? "url(#arrow-active)" : "url(#arrow)"}
                  stroke={isEdgeActive ? "#7c93ff" : "#1f1f25"}
                  strokeWidth={isEdgeActive ? 1.5 : 1}
                  strokeOpacity={isEdgeActive ? 0.9 : isDimmed ? 0.15 : 0.4}
                  className="transition-all duration-150"
                />
              );
            })}
          </g>

          {/* Nodes */}
          <g>
            {renderNodes.map((node) => {
              const isSelected = selectedNode?.id === node.id;
              const isHovered = hoveredNode?.id === node.id;
              const isHighlighted = activeNode && activeNeighbors.has(node.id);
              const isDimmed = activeNode && !activeNeighbors.has(node.id);

              // Assign a color based on node type / tags or section
              let nodeColor = "#55555f"; // faint text color
              if (node.section) {
                if (node.section.toLowerCase().includes("convers") || node.section.toLowerCase().includes("session")) {
                  nodeColor = "#3ecf8e"; // good green color
                } else {
                  nodeColor = "#7c93ff"; // accent blue color
                }
              } else if (node.tags && node.tags.length > 0) {
                nodeColor = "#7c93ff";
              }

              return (
                <g
                  key={node.id}
                  transform={`translate(${node.x}, ${node.y})`}
                  className="cursor-pointer"
                  onMouseDown={(e) => handleMouseDown(e, node.id)}
                  onMouseEnter={() => setHoveredNode(node)}
                  onMouseLeave={() => setHoveredNode(null)}
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedNode(isSelected ? null : node);
                  }}
                >
                  {/* Outer glowing halo on highlight */}
                  {(isSelected || isHovered || isHighlighted) && (
                    <circle
                      r={10}
                      fill="none"
                      stroke={isSelected ? "#7c93ff" : nodeColor}
                      strokeWidth={1.5}
                      strokeOpacity={isSelected ? 0.8 : 0.5}
                      className="animate-pulse"
                    />
                  )}

                  {/* Main Circle */}
                  <circle
                    r={isSelected ? 6.5 : 5}
                    fill={isSelected ? "#7c93ff" : nodeColor}
                    stroke="#101013"
                    strokeWidth={1}
                    opacity={isDimmed ? 0.3 : 1}
                    className="transition-all duration-150"
                  />

                  {/* Node label - only if selected/hovered/highlighted or label density is low */}
                  {(isSelected || isHovered || renderNodes.length <= 15) && (
                    <text
                      y={-12}
                      textAnchor="middle"
                      fill={isSelected || isHovered ? "#ededf2" : "#7d7d88"}
                      fontSize={9}
                      fontWeight={(isSelected || isHovered) ? "semibold" : "normal"}
                      opacity={isDimmed ? 0.25 : 1}
                      className="pointer-events-none select-none font-sans filter drop-shadow-[0_1px_2px_rgba(0,0,0,0.8)]"
                    >
                      {node.title}
                    </text>
                  )}
                </g>
              );
            })}
          </g>
        </svg>

        {/* Floating background click to clear selected */}
        {selectedNode && (
          <div
            className="absolute inset-0 -z-10 cursor-default"
            onClick={() => setSelectedNode(null)}
          />
        )}
      </div>

      {/* Footer Info Box */}
      <div className="border-t border-edge bg-panel2/40 p-2.5 flex flex-col gap-1 min-h-[50px]">
        {activeNode ? (
          <div>
            <div className="flex items-start justify-between gap-2">
              <span className="text-[11px] font-semibold text-txt truncate leading-tight block">
                {activeNode.title}
              </span>
              {activeNode.section && (
                <span className="text-[8px] uppercase tracking-wider text-accent bg-accent2/10 border border-accent/20 px-1 rounded shrink-0">
                  {activeNode.section}
                </span>
              )}
            </div>
            {activeNode.tags && activeNode.tags.length > 0 && (
              <div className="flex flex-wrap gap-0.5 mt-1">
                {activeNode.tags.map((tag, i) => (
                  <span key={i} className="text-[8px] text-faint px-1 bg-edge/40 rounded border border-edge/60">
                    #{tag}
                  </span>
                ))}
              </div>
            )}
            <div className="text-[8px] text-faint font-mono mt-1 uppercase tracking-wide">
              ID: <span className="text-muted select-all font-sans">{activeNode.id}</span>
            </div>
          </div>
        ) : (
          <div className="text-center text-faint text-[9px] uppercase tracking-wider py-1.5">
            Hover or click a page node to explore links
          </div>
        )}
      </div>
    </div>
  );
}
