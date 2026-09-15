import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ProofHire",
  description:
    "Evidence-grounded AI career agent for software engineers.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
