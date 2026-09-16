import { AppShell } from "@/components/app-shell";
import { CaptureHandoff } from "@/components/capture-handoff";

export default async function CapturePage({
  searchParams,
}: {
  searchParams: Promise<{ extension?: string; capture?: string }>;
}) {
  const params = await searchParams;
  return (
    <AppShell>
      <CaptureHandoff
        extensionId={
          typeof params.extension === "string" ? params.extension : ""
        }
        captureId={typeof params.capture === "string" ? params.capture : ""}
      />
    </AppShell>
  );
}
