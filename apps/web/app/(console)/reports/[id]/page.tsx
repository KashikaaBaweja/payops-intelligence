"use client";

import { usePathname } from "next/navigation";
import { ReportDetail } from "../../../../components/ReportDetail";

export default function ReportDetailPage() {
  const pathname = usePathname();
  const id = pathname.split("/").filter(Boolean).pop() || "";
  if (!id) {
    return null;
  }
  return <ReportDetail id={id} />;
}
