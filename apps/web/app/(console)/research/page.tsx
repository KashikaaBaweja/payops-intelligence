"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Dashboard } from "../../../components/Dashboard";
import { LoadingState } from "../../../components/states/PageState";

function ResearchInner() {
  const params = useSearchParams();
  const question = params.get("q") ?? undefined;
  const input = params.get("input") === "voice" ? "voice" : "text";
  return (
    <Dashboard
      initialQuestion={question}
      initialInputMethod={input}
      autoRun={params.get("run") === "1" && Boolean(question)}
    />
  );
}

export default function ResearchPage() {
  return (
    <Suspense fallback={<LoadingState label="Opening research workspace…" />}>
      <ResearchInner />
    </Suspense>
  );
}
