import Link from "next/link";

import { listResearchJobs, type JobListItem } from "@/lib/api";

export const dynamic = "force-dynamic";

function statusClasses(status: string): string {
  if (status === "done") {
    return "bg-emerald-100 text-emerald-700";
  }
  if (status === "failed") {
    return "bg-rose-100 text-rose-700";
  }
  return "bg-sky-100 text-sky-700";
}

export default async function DashboardPage() {
  const apiBaseUrl =
    process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

  let jobs: JobListItem[] = [];
  let loadError: string | null = null;

  try {
    jobs = await listResearchJobs();
  } catch {
    loadError =
      `Dashboard could not reach the research API at ${apiBaseUrl}. Start the backend and refresh this page.`;
  }

  return (
    <main className="space-y-6">
      <section className="rounded-[2rem] border border-white/70 bg-white/80 p-8 shadow-soft backdrop-blur">
        <p className="text-sm font-semibold uppercase tracking-[0.3em] text-ocean">
          Research Dashboard
        </p>
        <h1 className="mt-3 max-w-3xl text-4xl font-semibold tracking-tight text-ink">
          Launch Nepal GTM research jobs from a clean queue, then inspect live signals as they land.
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-7 text-slate-600">
          The backend runs live collectors, normalizes the evidence, and produces five structured research tabs plus a strategy brief.
        </p>
      </section>

      {loadError ? (
        <section className="rounded-[2rem] border border-amber-200 bg-amber-50/80 p-8 shadow-soft">
          <h2 className="text-2xl font-semibold text-amber-900">Backend is not running</h2>
          <p className="mt-3 text-amber-900/90">{loadError}</p>
          <p className="mt-4 text-sm text-amber-900/80">Run this from the project root:</p>
          <code className="mt-2 block rounded-xl bg-white/80 px-4 py-3 text-sm text-amber-900">
            uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
          </code>
          <p className="mt-4 text-sm text-amber-900/80">
            If your API is running elsewhere, set NEXT_PUBLIC_API_BASE_URL in your web environment and restart Next.js.
          </p>
        </section>
      ) : null}

      {!loadError && jobs.length === 0 ? (
        <section className="rounded-[2rem] border border-dashed border-ocean/30 bg-white/65 p-10 text-center shadow-soft">
          <h2 className="text-2xl font-semibold text-ink">No research jobs yet</h2>
          <p className="mt-3 text-slate-600">
            Start with a product brief and the agent will fetch live signals before building your Nepal market pack.
          </p>
          <Link
            href="/research/new"
            className="mt-6 inline-flex rounded-full bg-ocean px-5 py-3 font-medium text-white transition hover:bg-tide"
          >
            New Research
          </Link>
        </section>
      ) : !loadError ? (
        <section className="grid gap-4">
          {jobs.map((job) => (
            <Link
              key={job.job_id}
              href={`/research/${job.job_id}`}
              className="rounded-[1.5rem] border border-white/80 bg-white/80 p-6 shadow-soft transition hover:-translate-y-0.5 hover:border-ocean/20"
            >
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <h2 className="text-xl font-semibold text-ink">{job.product_name}</h2>
                  <p className="mt-1 text-sm text-slate-500">Job ID: {job.job_id}</p>
                  <p className="mt-3 text-sm text-slate-600">
                    Created {new Date(job.created_at).toLocaleString()}
                  </p>
                </div>
                <span
                  className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] ${statusClasses(job.status)}`}
                >
                  {job.status}
                </span>
              </div>
              {job.error ? (
                <p className="mt-4 text-sm text-rose-600">{job.error}</p>
              ) : null}
            </Link>
          ))}
        </section>
      ) : null}
    </main>
  );
}
