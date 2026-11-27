"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { SkeletonList } from "@proofhire/design-system/ui";
import { api, unwrap } from "@/lib/api-client";
import { qk, useApplications, useJobs, type Application } from "@/lib/queries";
import { useSession } from "@/lib/session";
import { DEMO_READ_ONLY, RequireSession } from "./session-ui";

const STAGES: Application["stage"][] = [
  "saved", "analyzing", "ready", "applied", "screen", "interview", "offer", "rejected", "archived",
];

/**
 * Application tracking (PRD §13 Application, §37 item 16 "revisit the
 * application later"): a list with a stage per job.
 */
export function ApplicationsBoard() {
  return (
    <RequireSession what="track your applications">
      <Board />
    </RequireSession>
  );
}

function Board() {
  const { canWrite } = useSession();
  const queryClient = useQueryClient();
  const applications = useApplications();
  const jobs = useJobs();

  const track = useMutation({
    mutationFn: async (jobId: string) =>
      unwrap(await api.POST("/api/v1/applications", { body: { job_id: jobId } })),
    onSuccess: (created) =>
      queryClient.setQueryData<Application[]>(qk.applications, (list = []) =>
        list.some((a) => a.id === created.id) ? list : [created, ...list],
      ),
    onSettled: () => queryClient.invalidateQueries({ queryKey: qk.overview }),
  });
  const setStage = useMutation({
    mutationFn: async ({ id, stage }: { id: string; stage: Application["stage"] }) =>
      unwrap(
        await api.PATCH("/api/v1/applications/{application_id}", {
          params: { path: { application_id: id } },
          body: { stage },
        }),
      ),
    // Optimistic: a stage change is the user's own decision about their own
    // record, so it shows immediately and rolls back only if the server
    // refuses. Waiting on the round trip made the dropdown feel stuck.
    onMutate: async ({ id, stage }) => {
      await queryClient.cancelQueries({ queryKey: qk.applications });
      const previous = queryClient.getQueryData<Application[]>(qk.applications);
      queryClient.setQueryData<Application[]>(qk.applications, (list) =>
        list?.map((a) => (a.id === id ? { ...a, stage } : a)),
      );
      return { previous };
    },
    onError: (_err, _vars, context) =>
      queryClient.setQueryData(qk.applications, context?.previous),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: qk.applications });
      void queryClient.invalidateQueries({ queryKey: qk.overview });
    },
  });

  if (applications.isPending || jobs.isPending) return <SkeletonList count={3} />;
  if (applications.isError || jobs.isError)
    return (
      <p className="ph-error" role="alert">
        Couldn&apos;t load applications. {(applications.error ?? jobs.error)?.message}
      </p>
    );

  const jobsById = Object.fromEntries(jobs.data.map((j) => [j.id, j]));
  const untracked = jobs.data.filter((j) => !applications.data.some((a) => a.job_id === j.id));
  const label = (jobId: string) => {
    const job = jobsById[jobId];
    return job ? `${job.role || "Untitled"}${job.company ? ` @ ${job.company}` : ""}` : jobId;
  };

  return (
    <div className="space-y-4">
      {[track, setStage].map(
        (m, i) =>
          m.isError && (
            <p key={i} className="ph-error" role="alert">
              {m.error.message}
            </p>
          ),
      )}

      {untracked.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs text-neutral-500">Jobs not yet tracked:</p>
          {untracked.map((job) => (
            <button
              key={job.id}
              type="button"
              className="ph-button mr-2"
              disabled={!canWrite || track.isPending}
              title={!canWrite ? DEMO_READ_ONLY : undefined}
              onClick={() => track.mutate(job.id)}
            >
              + Track: {label(job.id)}
            </button>
          ))}
        </div>
      )}

      <ul className="space-y-2">
        {applications.data.map((app) => (
          <li key={app.id} className="ph-source flex items-center justify-between gap-3 text-sm">
            <span>{label(app.job_id)}</span>
            <label className="ph-field ph-field-inline">
              <span className="sr-only">Stage for {label(app.job_id)}</span>
              <select
                value={app.stage}
                disabled={!canWrite}
                title={!canWrite ? DEMO_READ_ONLY : undefined}
                onChange={(e) =>
                  setStage.mutate({ id: app.id, stage: e.target.value as Application["stage"] })
                }
              >
                {STAGES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </label>
          </li>
        ))}
      </ul>

      {applications.data.length === 0 && (
        <p className="text-sm text-neutral-500">
          No tracked applications yet
          {jobs.data.length === 0 ? " — analyze a job first." : "."}
        </p>
      )}
    </div>
  );
}
