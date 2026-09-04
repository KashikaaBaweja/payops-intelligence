import "./globals.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "PayOps Intelligence",
  description: "Payment operations investigation agent",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
