"use client";

import { Html, Line, OrbitControls } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState } from "react";
import type { Mesh } from "three";
import { AgentRunLog } from "./AgentRunLog";
import { lightingFromLines, linesFromTrace, SETTLEMENT_DEMO_LOG } from "../../lib/runLog";
import type { GraphId } from "../../lib/runLog";
import type { StageId, StageState } from "../../lib/trace";
import type { TraceEvent } from "../../lib/types";

type GraphNode = {
  id: GraphId;
  label: string;
  position: [number, number, number];
};

const NODES: GraphNode[] = [
  { id: "researcher", label: "RESEARCHER", position: [0, 2.35, 0.2] },
  { id: "rag", label: "RAG", position: [-1.85, 1.15, 0.25] },
  { id: "planner", label: "ORCH", position: [0, 1.15, 0] },
  { id: "analyst", label: "DATA", position: [1.85, 1.15, 0.25] },
  { id: "evidence", label: "EVIDENCE", position: [-1.25, 0.05, 0.35] },
  { id: "integrity", label: "TXN", position: [0, 0.05, 0.15] },
  { id: "risk", label: "ML", position: [1.25, 0.05, 0.35] },
  { id: "classification", label: "REGRESS", position: [2.05, -0.55, 0.55] },
  { id: "critic", label: "CRITIC", position: [0, -1.25, 0] },
  { id: "writer", label: "REPORT", position: [0, -2.4, 0] },
];

const EDGES: [GraphId, GraphId][] = [
  ["researcher", "rag"],
  ["researcher", "planner"],
  ["researcher", "analyst"],
  ["rag", "planner"],
  ["planner", "analyst"],
  ["rag", "evidence"],
  ["planner", "integrity"],
  ["analyst", "risk"],
  ["evidence", "integrity"],
  ["integrity", "risk"],
  ["risk", "classification"],
  ["integrity", "critic"],
  ["risk", "critic"],
  ["critic", "writer"],
];

const COLOR = {
  pending: "#3a5278",
  active: "#3ee0b0",
  complete: "#3dd68c",
  skipped: "#1c2a3f",
};

function lookup(id: GraphId): GraphNode {
  return NODES.find((node) => node.id === id) ?? NODES[0];
}

function graphStates(
  stages: Record<StageId, StageState> | undefined,
  lighting: { active: GraphId[]; complete: GraphId[] } | null,
): Record<GraphId, StageState> {
  const next = {} as Record<GraphId, StageState>;
  for (const node of NODES) {
    if (lighting) {
      if (lighting.active.includes(node.id) || (node.id === "classification" && lighting.active.includes("risk"))) {
        next[node.id] = "active";
      } else if (lighting.complete.includes(node.id) || (node.id === "classification" && lighting.complete.includes("risk"))) {
        next[node.id] = "complete";
      } else {
        next[node.id] = "pending";
      }
      continue;
    }
    if (node.id === "evidence") {
      next[node.id] = stages?.rag ?? "pending";
      continue;
    }
    if (node.id === "classification") {
      next[node.id] = stages?.risk ?? "pending";
      continue;
    }
    if (node.id === "query") {
      next[node.id] = "pending";
      continue;
    }
    next[node.id] = stages?.[node.id] ?? "pending";
  }
  return next;
}

function AgentNode({
  node,
  state,
  selected,
  onSelect,
  reduceMotion,
}: {
  node: GraphNode;
  state: StageState;
  selected: boolean;
  onSelect: (id: GraphId) => void;
  reduceMotion: boolean;
}) {
  const mesh = useRef<Mesh>(null);
  const glow = COLOR[state];

  useFrame((frame) => {
    if (!mesh.current) {
      return;
    }
    if (reduceMotion) {
      mesh.current.scale.setScalar(1);
      return;
    }
    const pulse = state === "active" ? 1 + Math.sin(frame.clock.elapsedTime * 5) * 0.12 : 1;
    mesh.current.scale.setScalar(pulse);
  });

  return (
    <group position={node.position}>
      <mesh
        ref={mesh}
        onClick={(event) => {
          event.stopPropagation();
          onSelect(node.id);
        }}
      >
        <sphereGeometry args={[0.16, 32, 32]} />
        <meshStandardMaterial
          color={glow}
          emissive={glow}
          emissiveIntensity={state === "active" ? 1.4 : state === "complete" ? 0.55 : 0.08}
          roughness={0.28}
          metalness={0.35}
        />
      </mesh>
      {state === "active" ? (
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0.24, 0.3, 40]} />
          <meshBasicMaterial color={COLOR.active} transparent opacity={0.55} />
        </mesh>
      ) : null}
      <Html center distanceFactor={7} zIndexRange={[10, 0]}>
        <button
          type="button"
          className={`graph-label ${state} ${selected ? "is-selected" : ""}`}
          onClick={() => onSelect(node.id)}
        >
          {node.label}
        </button>
      </Html>
    </group>
  );
}

function AgentScene({
  states,
  selected,
  onSelect,
  reduceMotion,
}: {
  states: Record<GraphId, StageState>;
  selected: GraphId;
  onSelect: (id: GraphId) => void;
  reduceMotion: boolean;
}) {
  return (
    <>
      <color attach="background" args={["#070b14"]} />
      <ambientLight intensity={0.45} />
      <pointLight position={[2.4, 3.2, 3]} intensity={18} color="#3ee0b0" distance={12} />
      <pointLight position={[-3, -1, 2]} intensity={8} color="#4c8dff" distance={10} />
      {EDGES.map(([from, to]) => {
        const a = lookup(from);
        const b = lookup(to);
        const live =
          states[from] === "active" ||
          states[to] === "active" ||
          (states[from] === "complete" && states[to] === "complete");
        return (
          <Line
            key={`${from}-${to}`}
            points={[a.position, b.position]}
            color={live ? COLOR.active : "#2a3d5c"}
            lineWidth={live ? 2.2 : 1.1}
            transparent
            opacity={live ? 0.95 : 0.45}
          />
        );
      })}
      {NODES.map((node) => (
        <AgentNode
          key={node.id}
          node={node}
          state={states[node.id]}
          selected={selected === node.id}
          onSelect={onSelect}
          reduceMotion={reduceMotion}
        />
      ))}
      <OrbitControls
        enablePan={false}
        enableZoom={false}
        autoRotate={!reduceMotion}
        autoRotateSpeed={0.55}
        minPolarAngle={0.85}
        maxPolarAngle={1.45}
      />
    </>
  );
}

export function AgentGraph({
  states,
  events = [],
  question,
  demo = false,
  caption,
}: {
  states?: Record<StageId, StageState>;
  events?: TraceEvent[];
  question?: string;
  demo?: boolean;
  caption?: string;
}) {
  const [mounted, setMounted] = useState(false);
  const [cursor, setCursor] = useState(demo ? 1 : 0);
  const [selected, setSelected] = useState<GraphId>("planner");
  const [reduce, setReduce] = useState(false);

  const lines = useMemo(
    () => (demo ? SETTLEMENT_DEMO_LOG : linesFromTrace(events, question)),
    [demo, events, question],
  );

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduce(media.matches);
    const onChange = () => setReduce(media.matches);
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  useEffect(() => {
    if (!demo) {
      setCursor(lines.length);
      return;
    }
    if (reduce) {
      setCursor(lines.length);
      return;
    }
    setCursor(1);
    const timer = window.setInterval(() => {
      setCursor((value) => (value >= lines.length ? 1 : value + 1));
    }, 1100);
    return () => window.clearInterval(timer);
  }, [demo, reduce, lines.length]);

  const lighting = useMemo(
    () => (demo ? lightingFromLines(lines, cursor) : null),
    [demo, lines, cursor],
  );
  const graph = useMemo(() => graphStates(states, lighting), [states, lighting]);
  const current = lines[Math.max(0, cursor - 1)];
  const title = demo ? current?.agent || "Research running" : caption || "Agent architecture";
  const path = current ? `${current.agent} → ${current.detail}` : "Idle";

  return (
    <div className="graph-scene">
      <div className="graph-caption" aria-live="polite">
        <strong>{title}</strong>
        <span>{path}</span>
      </div>
      <div className="graph-shell">
        <div className="graph-canvas" role="img" aria-label={`${title}. ${path}`}>
          {mounted ? (
            <Canvas
              camera={{ position: [0.15, 0.2, 7.2], fov: 42 }}
              dpr={[1, 1.75]}
              gl={{ antialias: true, alpha: false }}
            >
              <AgentScene
                states={graph}
                selected={selected}
                onSelect={setSelected}
                reduceMotion={reduce}
              />
            </Canvas>
          ) : null}
        </div>
        <AgentRunLog lines={lines} cursor={cursor} />
      </div>
    </div>
  );
}
