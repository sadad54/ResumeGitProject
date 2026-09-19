"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { CommandPalette } from "./command-palette";

const NAV_ITEMS = [
  { href: "/", label: "Overview", symbol: "◈" },
  { href: "/evidence", label: "Evidence", symbol: "✧" },
  { href: "/jobs", label: "Job workspace", symbol: "◎" },
  { href: "/applications", label: "Applications", symbol: "▤" },
  { href: "/documents", label: "Documents", symbol: "▧" },
  { href: "/settings", label: "Settings", symbol: "⚙" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  useEffect(() => {
    let dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    try {
      const saved = localStorage.getItem("proofhire.theme");
      if (saved) dark = saved === "dark";
    } catch {
      /* use system preference */
    }
    document.documentElement.classList.toggle("dark", dark);
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }, []);
  return (
    <div className="ph-shell">
      <a className="ph-skip" href="#main-content">
        Skip to content
      </a>
      <aside className="ph-sidebar">
        <Link href="/" className="ph-brand">
          <span aria-hidden="true">
            p<span className="ph-accent">h</span>
          </span>
          ProofHire
        </Link>
        <p className="ph-sidebar-label">CAREER WORKSPACE</p>
        <nav aria-label="Primary">
          <ul>
            {NAV_ITEMS.map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  aria-current={pathname === item.href ? "page" : undefined}
                >
                  <span aria-hidden="true">{item.symbol}</span>
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <div className="ph-sidebar-footer">
          <span className="ph-eyebrow">Built on proof</span>
          <p>
            Your experience.
            <br />
            Every claim, grounded.
          </p>
        </div>
      </aside>
      <div className="ph-main">
        <header className="ph-topbar">
          <span>
            Workspace <span aria-hidden="true">/</span>{" "}
            <strong>
              {NAV_ITEMS.find((n) => n.href === pathname)?.label || "ProofHire"}
            </strong>
          </span>
          <CommandPalette />
        </header>
        <main id="main-content" tabIndex={-1}>
          {children}
        </main>
      </div>
    </div>
  );
}
