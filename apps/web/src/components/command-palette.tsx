"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, getAccessToken } from "@/lib/api";
import { Button } from "@proofhire/design-system/ui";

export function CommandPalette() {
  const dialog = useRef<HTMLDialogElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  function open() {
    setQuery("");
    dialog.current?.showModal();
    input.current?.focus();
  }
  function close() {
    dialog.current?.close();
  }
  function go(url: string) {
    close();
    router.push(url);
  }
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        if (dialog.current?.open) close();
        else open();
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  async function sync() {
    if (!getAccessToken()) {
      setMessage("Log in on Home before syncing.");
      return;
    }
    setBusy(true);
    try {
      const repos = await apiFetch<{ id: string; selected: boolean }[]>(
        "/api/v1/github/repositories",
      );
      const ids = repos.filter((r) => r.selected).map((r) => r.id);
      if (!ids.length) {
        setMessage("Select repositories on Home first.");
        return;
      }
      const run = await apiFetch<{ run_id: string }>("/api/v1/github/sync", {
        method: "POST",
        body: JSON.stringify({ repository_ids: ids }),
      });
      setMessage(
        `GitHub sync queued. Run ${run.run_id.slice(0, 8)}. Revisit Evidence when complete.`,
      );
      close();
    } catch {
      setMessage("Sync failed. Check your connection and try again.");
    } finally {
      setBusy(false);
    }
  }
  function toggleTheme() {
    const dark = !document.documentElement.classList.contains("dark");
    document.documentElement.classList.toggle("dark", dark);
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    try {
      localStorage.setItem("proofhire.theme", dark ? "dark" : "light");
    } catch {
      /* session only */
    }
    close();
  }
  const commands = [
    {
      label: "Analyze job",
      detail: "Capture a new job description",
      id: "job",
    },
    {
      label: "Sync GitHub",
      detail: "Sync your selected repositories",
      id: "sync",
    },
    {
      label: "Search evidence",
      detail: "Search your source-backed work",
      id: "evidence",
    },
    {
      label: "Open application",
      detail: "Revisit tracked applications",
      id: "application",
    },
    {
      label: "Export resume",
      detail: "Open a document and export its PDF",
      id: "export",
    },
    {
      label: "Change template",
      detail: "Choose the layout for your next export",
      id: "template",
    },
    {
      label: "Toggle theme",
      detail: "Switch light / dark appearance",
      id: "theme",
    },
  ].filter((c) =>
    `${c.label} ${c.detail}`.toLowerCase().includes(query.toLowerCase()),
  );
  async function run(id?: string) {
    if (id === "sync") return sync();
    if (id === "theme") return toggleTheme();
    const routes: Record<string, string> = {
      job: "/jobs#capture",
      evidence: "/evidence#review",
      application: "/applications",
      export: "/documents#export",
      template: "/documents#template",
    };
    if (id && routes[id]) go(routes[id]);
  }
  return (
    <>
      <Button className="ph-command-trigger" onClick={open}>
        Search & actions <kbd>⌘ / Ctrl K</kbd>
      </Button>
      <dialog
        ref={dialog}
        className="ph-dialog"
        aria-labelledby="command-title"
      >
        <div className="ph-toolbar">
          <h2 id="command-title">What’s next?</h2>
          <Button onClick={close} aria-label="Close command palette">
            Esc
          </Button>
        </div>
        <label className="ph-field">
          Search commands
          <input
            ref={input}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Type an action…"
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                dialog.current
                  ?.querySelector<HTMLButtonElement>(".ph-command-list button")
                  ?.focus();
              }
              if (e.key === "Enter") void run(commands[0]?.id);
            }}
          />
        </label>
        <ul
          className="ph-command-list"
          onKeyDown={(e) => {
            if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(e.key))
              return;
            e.preventDefault();
            const buttons = [
              ...e.currentTarget.querySelectorAll<HTMLButtonElement>(
                "button:not(:disabled)",
              ),
            ];
            const index = buttons.indexOf(
              document.activeElement as HTMLButtonElement,
            );
            const next =
              e.key === "Home"
                ? 0
                : e.key === "End"
                  ? buttons.length - 1
                  : (index +
                      (e.key === "ArrowDown" ? 1 : -1) +
                      buttons.length) %
                    buttons.length;
            buttons[next]?.focus();
          }}
        >
          {commands.map((c) => (
            <li key={c.label}>
              <button disabled={busy} onClick={() => void run(c.id)}>
                <strong>{c.label}</strong>
                <span>{c.detail}</span>
                <span aria-hidden="true">↗</span>
              </button>
            </li>
          ))}
        </ul>
        {!commands.length && <p>No matching commands.</p>}
        {message && <p role="status">{message}</p>}
      </dialog>
      <span className="ph-toast" role="status">
        {message}
      </span>
    </>
  );
}
