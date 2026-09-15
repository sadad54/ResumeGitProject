import { AppShell } from "@/components/app-shell";

export default function SettingsPage() {
  return (
    <AppShell>
      <h1 className="text-xl font-semibold">Settings</h1>
      <p className="mt-2 text-sm text-neutral-500">
        GitHub connection management, repo processing controls, and account
        settings land starting Phase 1.
      </p>
    </AppShell>
  );
}
