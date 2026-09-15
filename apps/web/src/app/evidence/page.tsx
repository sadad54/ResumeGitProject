import { AppShell } from "@/components/app-shell";
import { EvidenceExplorer } from "@/components/evidence-explorer";

export default function EvidencePage() {
  return (
    <AppShell>
      <h1 className="text-xl font-semibold">Evidence</h1>
      <p className="mt-2 text-sm text-neutral-500">
        Constellation graph view lands in Phase 7 — this is the Explorer list.
      </p>
      <div className="mt-4">
        <EvidenceExplorer />
      </div>
    </AppShell>
  );
}
