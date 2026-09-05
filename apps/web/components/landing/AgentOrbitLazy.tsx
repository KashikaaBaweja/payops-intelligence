"use client";

import dynamic from "next/dynamic";

export const AgentOrbit = dynamic(
  () => import("./AgentOrbit").then((module) => module.AgentOrbit),
  { ssr: false, loading: () => <div className="graph-scene" aria-hidden /> },
);
