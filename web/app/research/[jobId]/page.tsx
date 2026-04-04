import { Suspense } from "react";
import { notFound } from "next/navigation";

import { getResearchJob, getResearchResult } from "@/lib/api";

import { ResearchJobClient } from "./ResearchJobClient";

export const dynamic = "force-dynamic";

async function ResearchJobSection({ jobId }: { jobId: string }) {
  try {
    const job = await getResearchJob(jobId);
    const result = job.status === "done" ? await getResearchResult(jobId) : null;
    return <ResearchJobClient jobId={jobId} initialJob={job} initialResult={result} />;
  } catch {
    notFound();
  }
}

export default function ResearchJobPage({
  params,
}: {
  params: { jobId: string };
}) {
  return (
    <Suspense
      fallback={
        <div className="rounded-[2rem] border border-white/80 bg-white/85 p-8 shadow-soft">
          <p className="text-sm font-semibold uppercase tracking-[0.3em] text-ocean">
            Loading job
          </p>
          <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100">
            <div className="h-full w-1/3 animate-pulse rounded-full bg-gradient-to-r from-ocean to-tide" />
          </div>
        </div>
      }
    >
      <ResearchJobSection jobId={params.jobId} />
    </Suspense>
  );
}
