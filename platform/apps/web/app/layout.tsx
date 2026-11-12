import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PrepEzy | Adaptive Foundation",
  description: "A real, server-graded adaptive learning prototype for synthetic accounts.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
