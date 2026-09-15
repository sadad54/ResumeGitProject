import { AppShell } from "@/components/app-shell";
import { JobWorkspace } from "@/components/job-workspace";

export default function JobsPage() {
  return (
    <AppShell>
      <h1 className="text-xl font-semibold">Jobs</h1>
      <p className="mt-2 text-sm text-neutral-500">
        Coverage matrix and positioning land in Phase 4-5 — this is JD capture
        and requirement extraction.
      </p>
      <div className="mt-4">
        <JobWorkspace />
      </div>
    </AppShell>
  );
}
