"use client";

import { useState } from "react";
import { useFormStatus } from "react-dom";

import { submitResearchAction } from "./actions";

function SubmitButton() {
  const { pending } = useFormStatus();

  return (
    <button
      type="submit"
      disabled={pending}
      className="inline-flex items-center justify-center rounded-full bg-ocean px-5 py-3 font-medium text-white transition hover:bg-tide disabled:cursor-not-allowed disabled:opacity-70"
    >
      {pending ? "Launching research..." : "Launch research"}
    </button>
  );
}

export function NewResearchForm() {
  const [competitors, setCompetitors] = useState<string[]>([]);
  const [draftCompetitor, setDraftCompetitor] = useState("");

  function addCompetitor() {
    const next = draftCompetitor.trim();
    if (!next) {
      return;
    }
    setCompetitors((current) => Array.from(new Set([...current, next])));
    setDraftCompetitor("");
  }

  function removeCompetitor(label: string) {
    setCompetitors((current) => current.filter((item) => item !== label));
  }

  return (
    <form action={submitResearchAction} className="space-y-6 rounded-[2rem] border border-white/80 bg-white/85 p-8 shadow-soft backdrop-blur">
      <div>
        <p className="text-sm font-semibold uppercase tracking-[0.3em] text-ocean">
          New Research Brief
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-ink">
          Describe the product, target buyers, and competitive frame.
        </h1>
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        <label className="grid gap-2 text-sm font-medium text-slate-700">
          Product Name
          <input
            required
            name="product_name"
            className="rounded-2xl border border-slate-200 bg-white px-4 py-3 outline-none ring-0 transition focus:border-ocean"
            placeholder="ShopChat AI"
          />
        </label>
        <label className="grid gap-2 text-sm font-medium text-slate-700">
          Pricing Model
          <input
            required
            name="pricing_model"
            className="rounded-2xl border border-slate-200 bg-white px-4 py-3 outline-none ring-0 transition focus:border-ocean"
            placeholder="Monthly subscription with setup fee"
          />
        </label>
        <label className="grid gap-2 text-sm font-medium text-slate-700 md:col-span-2">
          Research Mode
          <select
            name="mode"
            defaultValue="free_first"
            className="rounded-2xl border border-slate-200 bg-white px-4 py-3 outline-none ring-0 transition focus:border-ocean"
          >
            <option value="free_first">Free First: Tavily basic search → DuckDuckGo fallback, real URLs + relevance scores</option>
            <option value="fast_draft">Fast Draft: AI hypotheses only, no live citations</option>
            <option value="grounded_paid">Grounded Paid: Tavily advanced search, deeper page content, higher signal quality</option>
          </select>
        </label>
      </div>

      <label className="grid gap-2 text-sm font-medium text-slate-700">
        Product Description
        <textarea
          required
          name="product_description"
          rows={5}
          className="rounded-[1.5rem] border border-slate-200 bg-white px-4 py-3 outline-none transition focus:border-ocean"
          placeholder="A hosted WhatsApp chatbot that answers in Nepali and English using shop inventory data."
        />
      </label>

      <label className="grid gap-2 text-sm font-medium text-slate-700">
        Target Customer Guess
        <textarea
          required
          name="target_customer_guess"
          rows={4}
          className="rounded-[1.5rem] border border-slate-200 bg-white px-4 py-3 outline-none transition focus:border-ocean"
          placeholder="Retail shops in Kathmandu, Lalitpur, and Pokhara that already handle customer questions on WhatsApp."
        />
      </label>

      <div className="grid gap-2 text-sm font-medium text-slate-700">
        <span>Competitors</span>
        <div className="flex flex-col gap-3 rounded-[1.5rem] border border-slate-200 bg-white p-4">
          <div className="flex flex-col gap-3 sm:flex-row">
            <input
              value={draftCompetitor}
              onChange={(event) => setDraftCompetitor(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  addCompetitor();
                }
              }}
              className="min-w-0 flex-1 rounded-2xl border border-slate-200 px-4 py-3 outline-none transition focus:border-ocean"
              placeholder="Custom software agencies"
            />
            <button
              type="button"
              onClick={addCompetitor}
              className="rounded-full border border-ocean/20 px-4 py-3 font-medium text-ocean transition hover:bg-skywash"
            >
              Add competitor
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {competitors.length === 0 ? (
              <p className="text-sm text-slate-500">Add a few known alternatives or substitutes.</p>
            ) : (
              competitors.map((competitor) => (
                <button
                  key={competitor}
                  type="button"
                  onClick={() => removeCompetitor(competitor)}
                  className="rounded-full bg-skywash px-3 py-2 text-sm text-ocean transition hover:bg-mist"
                >
                  {competitor} x
                </button>
              ))
            )}
          </div>
        </div>
        <input type="hidden" name="competitors_json" value={JSON.stringify(competitors)} />
      </div>

      <label className="grid gap-2 text-sm font-medium text-slate-700">
        Research Goal
        <textarea
          required
          name="research_goal"
          rows={4}
          className="rounded-[1.5rem] border border-slate-200 bg-white px-4 py-3 outline-none transition focus:border-ocean"
          placeholder="Identify the best initial shop segments, channels, and pricing expectations for launch."
        />
      </label>

      <div className="flex items-center justify-between gap-4 border-t border-slate-100 pt-2">
        <p className="max-w-2xl text-sm text-slate-500">
          Free First keeps real URLs in the output while limiting web calls. Fast Draft skips live evidence for the fastest response.
        </p>
        <SubmitButton />
      </div>
    </form>
  );
}
