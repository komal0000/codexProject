"use client";

import { startTransition, useEffect, useMemo, useState } from "react";

import {
  getResearchJob,
  getResearchResult,
  type JobStatus,
  type ResearchResult,
} from "@/lib/api";

type ResearchJobClientProps = {
  jobId: string;
  initialJob: JobStatus;
  initialResult: ResearchResult | null;
};

function statusClasses(status: JobStatus["status"]): string {
  if (status === "done") {
    return "bg-emerald-100 text-emerald-700";
  }
  if (status === "failed") {
    return "bg-rose-100 text-rose-700";
  }
  return "bg-sky-100 text-sky-700";
}

function renderSummary(summary: string) {
  return summary.split("\n").map((line, index) => {
    const value = line.trim();
    if (!value) {
      return <div key={`spacer-${index}`} className="h-2" />;
    }
    if (value.startsWith("# ")) {
      return <h2 key={index} className="text-2xl font-semibold text-ink">{value.slice(2)}</h2>;
    }
    if (value.startsWith("## ")) {
      return <h3 key={index} className="mt-4 text-lg font-semibold text-ink">{value.slice(3)}</h3>;
    }
    if (value.startsWith("- ")) {
      return <p key={index} className="pl-4 text-sm leading-7 text-slate-700">• {value.slice(2)}</p>;
    }
    return <p key={index} className="text-sm leading-7 text-slate-700">{value}</p>;
  });
}

function toCsv(rows: Array<Record<string, string | number | null>>): string {
  if (rows.length === 0) {
    return "empty\n";
  }
  const headers = Object.keys(rows[0]);
  const lines = [headers.join(",")];
  for (const row of rows) {
    lines.push(
      headers
        .map((header) => {
          const raw = row[header] ?? "";
          const value = String(raw).replace(/"/g, "\"\"");
          return `"${value}"`;
        })
        .join(","),
    );
  }
  return `${lines.join("\n")}\n`;
}

export function ResearchJobClient({
  jobId,
  initialJob,
  initialResult,
}: ResearchJobClientProps) {
  const [job, setJob] = useState(initialJob);
  const [result, setResult] = useState<ResearchResult | null>(initialResult);
  const [pollError, setPollError] = useState<string | null>(null);

  useEffect(() => {
    if (job.status === "failed" || (job.status === "done" && result)) {
      return;
    }

    let cancelled = false;
    const timer = window.setInterval(async () => {
      try {
        const nextJob = await getResearchJob(jobId);
        if (cancelled) {
          return;
        }
        startTransition(() => {
          setJob(nextJob);
          setPollError(null);
        });

        if (nextJob.status === "done" && !result) {
          const nextResult = await getResearchResult(jobId);
          if (cancelled) {
            return;
          }
          startTransition(() => {
            setResult(nextResult);
          });
          window.clearInterval(timer);
        }
      } catch {
        if (cancelled) {
          return;
        }
        startTransition(() => {
          setPollError("Could not refresh job status. Retrying automatically every 3 seconds.");
        });
      }
    }, 3000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [job.status, jobId, result]);

  const orderedTabs = useMemo(
    () => (result ? Object.entries(result.tabs) : []),
    [result],
  );

  function downloadCsv(tabName: string, rows: Array<Record<string, string | number | null>>) {
    const blob = new Blob([toCsv(rows)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${tabName.toLowerCase().replace(/\s+/g, "_")}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  async function copySummary() {
    if (!result) {
      return;
    }
    await navigator.clipboard.writeText(result.strategy_summary);
  }

  return (
    <div className="space-y-6">
      <section className="rounded-[2rem] border border-white/80 bg-white/85 p-8 shadow-soft">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.3em] text-ocean">
              Research Job
            </p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-ink">
              {result?.brief.product_name ?? `Job ${jobId}`}
            </h1>
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

        {job.status !== "done" && job.status !== "failed" ? (
          <div className="mt-8 rounded-[1.5rem] border border-ocean/10 bg-skywash p-6">
            <div className="h-2 overflow-hidden rounded-full bg-white">
              <div className="h-full w-1/2 animate-pulse rounded-full bg-gradient-to-r from-ocean to-tide" />
            </div>
            <p className="mt-4 text-sm leading-7 text-slate-600">
              The backend is collecting live signals, normalizing them, and building the research tabs. This page polls every 3 seconds.
            </p>
            {pollError ? <p className="mt-3 text-sm text-amber-700">{pollError}</p> : null}
          </div>
        ) : null}

        {job.error ? <p className="mt-6 text-sm text-rose-600">{job.error}</p> : null}
      </section>

      {result ? (
        <>
          <section className="rounded-[2rem] border border-white/80 bg-white/85 p-8 shadow-soft">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-semibold uppercase tracking-[0.3em] text-ocean">
                  Strategy Summary
                </p>
                <p className="mt-2 text-sm text-slate-500">
                  {result.live_signals_count} live signals processed into {orderedTabs.length} research tabs.
                </p>
              </div>
              <button
                type="button"
                onClick={copySummary}
                className="rounded-full border border-ocean/20 px-4 py-2 text-sm font-medium text-ocean transition hover:bg-skywash"
              >
                Copy Summary
              </button>
            </div>
            <div className="mt-6 space-y-1">{renderSummary(result.strategy_summary)}</div>
          </section>

          <section className="space-y-5">
            {orderedTabs.map(([tabName, rows]) => (
              <div key={tabName} className="rounded-[2rem] border border-white/80 bg-white/85 p-6 shadow-soft">
                <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h2 className="text-xl font-semibold text-ink">{tabName}</h2>
                    <p className="text-sm text-slate-500">{rows.length} rows</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => downloadCsv(tabName, rows)}
                    className="rounded-full border border-ocean/20 px-4 py-2 text-sm font-medium text-ocean transition hover:bg-skywash"
                  >
                    Download CSV
                  </button>
                </div>
                <div className="overflow-x-auto">
                  <table className="min-w-full border-separate border-spacing-y-2 text-left text-sm">
                    <thead>
                      <tr>
                        {Object.keys(rows[0] ?? { empty: "" }).map((header) => (
                          <th key={header} className="px-3 py-2 font-semibold text-slate-500">
                            {header}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {(rows.length ? rows : [{ empty: "" }]).map((row, rowIndex) => (
                        <tr key={`${tabName}-${rowIndex}`} className="rounded-2xl bg-slate-50">
                          {Object.entries(row).map(([header, value]) => (
                            <td key={`${header}-${rowIndex}`} className="px-3 py-3 align-top text-slate-700">
                              {String(value ?? "")}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </section>
        </>
      ) : null}
    </div>
  );
}
