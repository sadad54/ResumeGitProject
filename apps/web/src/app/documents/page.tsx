import { AppShell } from "@/components/app-shell";
import { ResumeWorkspace } from "@/components/resume-workspace";

export default function DocumentsPage() {
  return (
    <AppShell>
      <h1 className="text-xl font-semibold">Documents</h1>
      <p className="mt-2 text-sm text-neutral-500">
        Generate, inspect and export application documents with claim-level provenance.
      </p>
      <div className="mt-4">
        <ResumeWorkspace />
      </div>
    </AppShell>
  );
}

