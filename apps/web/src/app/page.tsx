import { AppShell } from "@/components/app-shell";

export default function HomePage() {
  return (
    <AppShell>
      <h1 className="text-xl font-semibold">Home</h1>
      <p className="mt-2 text-sm text-neutral-500">
        GitHub sync status, evidence freshness, recent jobs, applications in
        progress, and &ldquo;Analyze a job&rdquo; land here starting Phase 1.
      </p>
    </AppShell>
  );
}
