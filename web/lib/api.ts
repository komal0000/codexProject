export type ResearchBrief = {
  product_name: string;
  product_description: string;
  target_customer_guess: string;
  pricing_model: string;
  competitor_examples: string[];
  research_goal: string;
};

export type JobStatus = {
  job_id: string;
  status: "queued" | "running" | "done" | "failed";
  created_at: string;
  completed_at: string | null;
  error: string | null;
};

export type JobListItem = JobStatus & {
  product_name: string;
};

export type JobCreateResponse = {
  job_id: string;
  status: "queued";
};

export type ResearchResult = {
  job_id: string;
  brief: ResearchBrief;
  tabs: Record<string, Array<Record<string, string | number | null>>>;
  strategy_summary: string;
  validation: Record<string, unknown>;
  sources_count: number;
  live_signals_count: number;
  created_at: string;
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    cache: "no-store",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    throw new Error(`API request failed (${response.status}) for ${path}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export async function listResearchJobs(): Promise<JobListItem[]> {
  return apiFetch<JobListItem[]>("/api/research");
}

export async function createResearchJob(
  brief: ResearchBrief,
): Promise<JobCreateResponse> {
  return apiFetch<JobCreateResponse>("/api/research", {
    method: "POST",
    body: JSON.stringify(brief),
  });
}

export async function getResearchJob(jobId: string): Promise<JobStatus> {
  return apiFetch<JobStatus>(`/api/research/${jobId}`);
}

export async function getResearchResult(jobId: string): Promise<ResearchResult> {
  return apiFetch<ResearchResult>(`/api/research/${jobId}/result`);
}

export async function deleteResearchJob(jobId: string): Promise<void> {
  await apiFetch<void>(`/api/research/${jobId}`, { method: "DELETE" });
}
