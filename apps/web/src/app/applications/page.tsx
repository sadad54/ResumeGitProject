import { AppShell } from "@/components/app-shell";
import { ApplicationsBoard } from "@/components/applications-board";

export default function ApplicationsPage() {
  return (
    <AppShell>
      <h1 className="text-xl font-semibold">Applications</h1>
      <p className="mt-2 text-sm text-neutral-500">
        Track stage progress for jobs you&apos;ve analyzed.
      </p>
      <div className="mt-4">
        <ApplicationsBoard />
      </div>
    </AppShell>
  );
}
