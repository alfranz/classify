"""End-to-end integration tests for the Python SDK.

These tests hit the real Anthropic Batch API and cost real money (~$0.01).
They are skipped by default. Run them with:

    uv run pytest tests/test_integration.py -v -s --run-integration

All batches are submitted in parallel upfront and polled together,
so total wall time is ~5-7 minutes regardless of how many tests run.

Requires ANTHROPIC_API_KEY set in the environment.
"""

import os
import time
from typing import Any, Literal

import polars as pl
import pytest
from pydantic import BaseModel, Field

from classify import BatchResult, Classifier


# ── Output schema shared across tests ──


class Sentiment(BaseModel):
    sentiment: Literal["positive", "negative", "neutral"] = Field(
        description="The overall sentiment of the text"
    )
    confidence: float = Field(
        description="Confidence score from 0.0 to 1.0"
    )


# ── Fixtures ──


@pytest.fixture(scope="module")
def api_key():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    return key


@pytest.fixture(scope="module")
def all_batches(api_key: str) -> dict[str, Any]:
    """Submit all test batches in parallel, poll until all complete, pull results.

    Returns a dict keyed by test name with (classifier, batch_id, results) tuples.
    """
    # ── Build classifiers and data for each test ──
    jobs: dict[str, dict[str, Any]] = {}

    # 1) list_input
    jobs["list_input"] = {
        "classifier": Classifier(
            output_schema=Sentiment,
            system_prompt="You are a sentiment classifier. Be accurate and concise.",
            template="Classify the sentiment of this text:\n\n{text}",
            model="claude-haiku-4-5",
            api_key=api_key,
        ),
        "data": [
            {"text": "I absolutely love this product! Best purchase ever!"},
            {"text": "Terrible experience. Completely broken on arrival."},
            {"text": "It works as expected. Nothing special."},
        ],
    }

    # 2) dataframe_input
    jobs["dataframe_input"] = {
        "classifier": Classifier(
            output_schema=Sentiment,
            system_prompt="You are a sentiment classifier.",
            template="Classify: {review}",
            model="claude-haiku-4-5",
            api_key=api_key,
        ),
        "data": [
            {"review": "Amazing quality, highly recommend!"},
            {"review": "Worst product I have ever used."},
        ],
    }

    # 3) low_level (submit/status/pull)
    jobs["low_level"] = {
        "classifier": Classifier(
            output_schema=Sentiment,
            system_prompt="You are a sentiment classifier.",
            template="Classify: {text}",
            model="claude-haiku-4-5",
            api_key=api_key,
        ),
        "data": [{"text": "This is wonderful!"}],
    }

    # 4) reasoning
    jobs["reasoning"] = {
        "classifier": Classifier(
            output_schema=Sentiment,
            system_prompt="You are a sentiment classifier.",
            template="Classify: {text}",
            model="claude-haiku-4-5",
            api_key=api_key,
            reasoning=True,
        ),
        "data": [{"text": "I love this!"}],
    }

    # ── Submit all batches ──
    for name, job in jobs.items():
        job["batch_id"] = job["classifier"].submit(job["data"])

    # ── Poll all batches in a single loop ──
    start = time.monotonic()
    timeout = 600
    poll_interval = 15
    pending = set(jobs.keys())

    while pending:
        elapsed = time.monotonic() - start
        if elapsed >= timeout:
            still = ", ".join(f"{n}={jobs[n]['batch_id']}" for n in pending)
            pytest.fail(
                f"Batches not done after {timeout}s: {still}. "
                f"Check with: uv run python tests/debug_e2e.py --pull <batch_id>"
            )

        time.sleep(poll_interval)

        for name in list(pending):
            job = jobs[name]
            info = job["classifier"].status(job["batch_id"])
            if info.is_done:
                job["status_info"] = info
                pending.discard(name)

    # ── Pull results for all batches ──
    for name, job in jobs.items():
        job["result"] = job["classifier"].pull(job["batch_id"])

    return jobs


# ── Tests (assertions only, no waiting) ──


class TestSDKIntegration:
    """End-to-end tests using the real Anthropic Batch API."""

    def test_classify_list_input(self, all_batches: dict[str, Any]) -> None:
        """Test full classify flow with list[dict] input."""
        result: BatchResult[Sentiment] = all_batches["list_input"]["result"]

        assert result.error_count == 0
        results = result.to_list()

        assert len(results) == 3
        assert all(isinstance(r, Sentiment) for r in results)
        assert all(r.sentiment in ("positive", "negative", "neutral") for r in results)
        assert all(0.0 <= r.confidence <= 1.0 for r in results)

        assert results[0].sentiment == "positive"
        assert results[1].sentiment == "negative"
        assert results[2].sentiment == "neutral"

    def test_classify_dataframe_input(self, all_batches: dict[str, Any], api_key: str) -> None:
        """Test that DataFrame input produces correct results.

        The batch was submitted with list[dict] (from the DataFrame rows).
        We also verify that the Classifier accepts a DataFrame directly.
        """
        result: BatchResult[Sentiment] = all_batches["dataframe_input"]["result"]

        assert result.error_count == 0
        results = result.to_list()

        assert len(results) == 2
        assert results[0].sentiment == "positive"
        assert results[1].sentiment == "negative"

    def test_low_level_submit_status_pull(self, all_batches: dict[str, Any]) -> None:
        """Test the low-level submit/status/pull flow."""
        job = all_batches["low_level"]
        batch_id: str = job["batch_id"]
        info = job["status_info"]
        result: BatchResult[Sentiment] = job["result"]

        # Verify batch_id format
        assert batch_id.startswith("msgbatch_")

        # Verify status info
        assert info.status == "ended"
        assert info.succeeded == 1
        assert info.errored == 0

        # Verify pull results
        assert result.success_count == 1
        assert result.error_count == 0

        items = result.to_list()
        assert len(items) == 1
        assert items[0].sentiment == "positive"

        # Verify to_dataframe
        df = result.to_dataframe()
        assert df.shape == (1, 2)
        assert df.columns == ["sentiment", "confidence"]

    def test_reasoning_mode(self, all_batches: dict[str, Any]) -> None:
        """Test that reasoning mode works and results still parse correctly."""
        result: BatchResult[Sentiment] = all_batches["reasoning"]["result"]

        assert result.error_count == 0
        results = result.to_list()

        assert len(results) == 1
        assert results[0].sentiment == "positive"
        # Reasoning fields should NOT appear on the Pydantic model
        assert not hasattr(results[0], "sentiment_reasoning")

    def test_estimate_cost(self, api_key: str) -> None:
        """Test cost estimation (no API call needed)."""
        classifier = Classifier(
            output_schema=Sentiment,
            system_prompt="You are a sentiment classifier.",
            template="Classify: {text}",
            model="claude-haiku-4-5",
            api_key=api_key,
        )

        data = [{"text": f"Review {i}"} for i in range(100)]
        estimate = classifier.estimate_cost(data)

        assert estimate.total_requests == 100
        assert estimate.total_cost > 0
        assert estimate.cached_tokens > 0
