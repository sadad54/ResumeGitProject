import { AccountSettings } from "@/components/account-settings";
import { AppShell } from "@/components/app-shell";
import { GitHubCallbackNotice } from "@/components/github-callback-notice";
import { GitHubPanel } from "@/components/github-panel";
import { ResumeUpload } from "@/components/resume-upload";
import { RequireSession } from "@/components/session-ui";

export default async function SettingsPage({
  searchParams,
}: {
  searchParams: Promise<{ github?: string }>;
}) {
  const { github } = await searchParams;
  return (
    <AppShell>
      <h1 className="text-xl font-semibold">Settings</h1>
      <GitHubCallbackNotice outcome={typeof github === "string" ? github : undefined} />
      <RequireSession what="manage your account">
        <div className="ph-settings">
          <section id="github" aria-labelledby="github-heading">
            <h2 id="github-heading">GitHub</h2>
            <GitHubPanel />
          </section>
          <section id="profile" aria-labelledby="profile-heading">
            <h2 id="profile-heading">Profile facts</h2>
            <p className="text-sm text-neutral-500">
              Upload a resume to extract employment and education facts. Once you confirm
              them, the fact guard checks every generated claim about employers, titles and
              dates against them.
            </p>
            <ResumeUpload />
          </section>
          <section id="account" aria-labelledby="account-heading">
            <h2 id="account-heading">Account</h2>
            <AccountSettings />
          </section>
        </div>
      </RequireSession>
    </AppShell>
  );
}
