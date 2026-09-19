import { AppShell } from "@/components/app-shell";
import { EvidenceExplorer } from "@/components/evidence-explorer";
import { EvidenceConstellation } from "@/components/evidence-constellation";

export default function EvidencePage() {
  return (
    <AppShell>
      <h1 className="sr-only">Evidence</h1>
      <EvidenceConstellation />
      <section id="review" className="ph-review">
        <h2>Review your evidence</h2>
        <p>
          Confirm what you can stand behind. Keep the rest private, or reject
          it.
        </p>
        <EvidenceExplorer />
      </section>
    </AppShell>
  );
}
