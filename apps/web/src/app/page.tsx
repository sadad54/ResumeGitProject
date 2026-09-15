import { AppShell } from "@/components/app-shell";
import { HomeContent } from "@/components/home-content";

export default function HomePage() {
  return (
    <AppShell>
      <h1 className="text-xl font-semibold">Home</h1>
      <p className="mt-2 text-sm text-neutral-500">
        Evidence freshness, recent jobs, and applications in progress land
        here starting Phase 2+. For now: connect GitHub and sync a repo.
      </p>
      <div className="mt-4">
        <HomeContent />
      </div>
    </AppShell>
  );
}
