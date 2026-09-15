import Link from "next/link";

const NAV_ITEMS = [
  { href: "/", label: "Home" },
  { href: "/evidence", label: "Evidence" },
  { href: "/jobs", label: "Jobs" },
  { href: "/applications", label: "Applications" },
  { href: "/documents", label: "Documents" },
  { href: "/settings", label: "Settings" },
] as const;

/**
 * Primary navigation shell (PRD §10). Static placeholder in Phase 0 — real
 * responsive layout, command palette, and loading/error states land in Phase 7 (C2).
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh">
      <nav className="w-56 shrink-0 border-r border-neutral-200 p-4 dark:border-neutral-800">
        <div className="mb-6 font-semibold">ProofHire</div>
        <ul className="space-y-1">
          {NAV_ITEMS.map((item) => (
            <li key={item.href}>
              <Link
                href={item.href}
                className="block rounded px-2 py-1.5 text-sm hover:bg-neutral-100 dark:hover:bg-neutral-900"
              >
                {item.label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
