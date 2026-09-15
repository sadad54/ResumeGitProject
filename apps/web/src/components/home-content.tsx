"use client";

import { useState } from "react";
import { AuthPanel } from "@/components/auth-panel";
import { GitHubPanel } from "@/components/github-panel";

export function HomeContent() {
  const [authVersion, setAuthVersion] = useState(0);

  return (
    <div className="space-y-6">
      <AuthPanel onAuthed={() => setAuthVersion((v) => v + 1)} />
      <GitHubPanel key={authVersion} />
    </div>
  );
}
