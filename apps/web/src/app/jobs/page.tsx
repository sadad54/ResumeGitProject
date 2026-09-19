import { AppShell } from "@/components/app-shell";
import { JobWorkspace } from "@/components/job-workspace";

export default async function JobsPage({
  searchParams,
}: {
  searchParams: Promise<{ job?: string }>;
}) {
  const params = await searchParams;
  return (
    <AppShell>
      <div className="ph-workspace-heading">
        <div>
          <span className="ph-eyebrow">The next chapter</span>
          <h1 className="text-3xl font-semibold mt-2">
            Find your fit<span className="ph-accent">.</span>
          </h1>
          <p className="mt-2">
            A job description meets the work you can prove.
          </p>
        </div>
      </div>
      <JobWorkspace
        initialJobId={typeof params.job === "string" ? params.job : ""}
      />
    </AppShell>
  );
}
