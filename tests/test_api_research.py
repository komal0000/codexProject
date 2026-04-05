from __future__ import annotations

import unittest

from api.models import JobRecord, ResearchBrief
from api.routes.research import JOB_STORE, run_research_job, utc_now, workspace_for_job


class APIResearchJobTests(unittest.IsolatedAsyncioTestCase):
    async def test_fast_draft_job_handles_empty_competitor_list(self) -> None:
        job_id = "test-fast-draft-empty-competitors"
        brief = ResearchBrief(
            product_name="AI WhatsApp chatbot for shops",
            product_description="Customers message a shop on WhatsApp and AI replies in Nepali/English.",
            target_customer_guess="Customer in morang for small shops",
            pricing_model="Monthly subscription",
            competitor_examples=[],
            research_goal="Identify the best shops and pricing",
        )
        JOB_STORE[job_id] = JobRecord(
            job_id=job_id,
            brief=brief,
            status="queued",
            mode="fast_draft",
            stage="queued",
            created_at=utc_now(),
            workspace=str(workspace_for_job(job_id)),
        )
        try:
            await run_research_job(job_id, brief)
            job = JOB_STORE[job_id]
            self.assertEqual(job.status, "done")
            self.assertEqual(job.stage, "complete")
            self.assertIsNotNone(job.result)
            self.assertEqual(job.result.mode, "fast_draft")
            self.assertEqual(job.result.citations_count, 0)
        finally:
            JOB_STORE.pop(job_id, None)


if __name__ == "__main__":
    unittest.main()
