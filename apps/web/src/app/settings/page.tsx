import { AppShell } from "@/components/app-shell";
import { ResumeUpload } from "@/components/resume-upload";

export default function SettingsPage() {
  return (
    <AppShell>
      <h1 className="text-xl font-semibold">Settings</h1>
      <p className="mt-2 text-sm text-neutral-500">
        GitHub connection management lives on Home for now. Upload a resume
        below to extract confirmed profile facts (employment, education) that
        the fact guard checks generated claims against.
      </p>
      <div className="mt-4">
        <ResumeUpload />
      </div>
    </AppShell>
  );
}
