"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Dashboard } from "../../../components/Dashboard";
import { LoadingState } from "../../../components/states/PageState";

function ResearchInner() {
  const params = useSearchParams();
  return <Dashboard initialQuestion={params.get("q") ?? undefined} />;
}

export default function ResearchPage() {
  return (
    <Suspense fallback={<LoadingState label="Opening research workspace…" />}>
      <ResearchInner />
    </Suspense>
  );
}
