"use server";

import { redirect } from "next/navigation";

import { createResearchJob, type ResearchBrief } from "@/lib/api";

function parseCompetitors(raw: string): string[] {
  if (!raw) {
    return [];
  }
  try {
    const parsed = JSON.parse(raw) as string[];
    return parsed.map((item) => item.trim()).filter(Boolean);
  } catch {
    return raw
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }
}

export async function submitResearchAction(formData: FormData) {
  const brief: ResearchBrief = {
    product_name: String(formData.get("product_name") ?? ""),
    product_description: String(formData.get("product_description") ?? ""),
    target_customer_guess: String(formData.get("target_customer_guess") ?? ""),
    pricing_model: String(formData.get("pricing_model") ?? ""),
    competitor_examples: parseCompetitors(String(formData.get("competitors_json") ?? "[]")),
    research_goal: String(formData.get("research_goal") ?? ""),
  };
  const response = await createResearchJob(brief);
  redirect(`/research/${response.job_id}`);
}
