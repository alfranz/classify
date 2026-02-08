"""Python SDK for classify - LLM-based classification using Claude's Batch API."""

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

import polars as pl
from pydantic import BaseModel

from classify.api.batch_client import BatchClient
from classify.core.models import MODEL_PRICING, CostEstimate
from classify.exceptions import ClassifyError, ClassifyTimeoutError
from classify.schema import infer_columns_from_template, pydantic_to_json_schema

T = TypeVar("T", bound=BaseModel)


@dataclass
class RowError:
    """Error for a single row in a batch."""

    row_index: int
    error: str
    raw_response: dict[str, Any] | None = None


@dataclass
class BatchInfo:
    """Status of a batch job."""

    batch_id: str
    status: str
    total: int
    succeeded: int
    errored: int

    @property
    def is_done(self) -> bool:
        return self.status in ("ended", "canceled", "errored")

    @property
    def progress(self) -> float:
        return (self.succeeded + self.errored) / self.total if self.total > 0 else 0.0


@dataclass
class BatchResult(Generic[T]):
    """Complete results from a batch job."""

    results: list[tuple[int, T]] = field(default_factory=list)
    errors: list[RowError] = field(default_factory=list)
    total: int = 0

    def to_list(self) -> list[T]:
        """Return results as ordered list. Raises if any errors exist."""
        if self.errors:
            raise ClassifyError(
                f"{len(self.errors)} row(s) failed. Access .errors for details."
            )
        sorted_results = sorted(self.results, key=lambda x: x[0])
        return [r for _, r in sorted_results]

    def to_dataframe(self) -> pl.DataFrame:
        """Return results as a polars DataFrame, ordered by row index.

        Raises if any errors exist.
        """
        items = self.to_list()
        if not items:
            return pl.DataFrame()
        return pl.DataFrame([item.model_dump() for item in items])

    @property
    def success_count(self) -> int:
        return len(self.results)

    @property
    def error_count(self) -> int:
        return len(self.errors)


class Classifier(Generic[T]):
    """LLM-based classifier using Claude's Batch API.

    Type parameter T is the output schema Pydantic model.
    """

    def __init__(
        self,
        output_schema: type[T],
        system_prompt: str,
        template: str,
        *,
        model: str = "claude-sonnet-4-5",
        reasoning: bool = False,
        batch_size: int = 10_000,
        api_key: str | None = None,
    ):
        self.output_schema = output_schema
        self.system_prompt = system_prompt
        self.template = template
        self.model = model
        self.reasoning = reasoning
        self.batch_size = batch_size

        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not self._api_key:
            raise ClassifyError(
                "API key required. Pass api_key or set ANTHROPIC_API_KEY env var."
            )

        self._columns = infer_columns_from_template(template)
        self._json_schema = pydantic_to_json_schema(output_schema, reasoning=reasoning)
        self._client = BatchClient(self._api_key)

    def classify(
        self,
        data: list[dict[str, Any]] | pl.DataFrame,
        *,
        poll_interval: float = 30.0,
        timeout: float | None = None,
    ) -> list[T]:
        """Submit data, poll until complete, return typed results.

        Args:
            data: Input rows as list of dicts or polars DataFrame.
            poll_interval: Seconds between status polls.
            timeout: Max seconds to wait. None = wait indefinitely.

        Returns:
            List of output_schema instances, one per input row, in input order.

        Raises:
            ClassifyError: If batch fails or has errors.
            ClassifyTimeoutError: If timeout exceeded.
        """
        batch_id = self.submit(data)

        start_time = time.monotonic()
        while True:
            info = self.status(batch_id)
            if info.is_done:
                break

            if timeout is not None:
                elapsed = time.monotonic() - start_time
                if elapsed >= timeout:
                    raise ClassifyTimeoutError(
                        f"Batch {batch_id} did not complete within {timeout}s. "
                        f"Progress: {info.succeeded}/{info.total}"
                    )

            time.sleep(poll_interval)

        if info.status == "errored":
            raise ClassifyError(f"Batch {batch_id} failed with status: {info.status}")

        result = self.pull(batch_id)
        return result.to_list()

    def submit(self, data: list[dict[str, Any]] | pl.DataFrame) -> str:
        """Submit batch job, return batch ID immediately.

        Args:
            data: Input rows as list of dicts or polars DataFrame.

        Returns:
            Batch ID string.
        """
        rows = self._normalize_input(data)
        requests = self._build_requests(rows)
        return self._client.create_batch_from_requests(requests)

    def status(self, batch_id: str) -> BatchInfo:
        """Check batch processing status.

        Args:
            batch_id: Batch ID from submit().

        Returns:
            BatchInfo with current status and progress.
        """
        batch_status, info = self._client.get_batch_status(batch_id)
        counts = info["request_counts"]
        return BatchInfo(
            batch_id=batch_id,
            status=batch_status.value,
            total=counts["succeeded"]
            + counts["errored"]
            + counts["processing"]
            + counts.get("canceled", 0)
            + counts.get("expired", 0),
            succeeded=counts["succeeded"],
            errored=counts["errored"],
        )

    def pull(self, batch_id: str) -> BatchResult[T]:
        """Download and parse results for a completed batch.

        Args:
            batch_id: Batch ID from submit().

        Returns:
            BatchResult with typed results and any errors.
        """
        raw_results = self._client.get_results_as_dicts(batch_id)
        return self._parse_results(raw_results)

    def cancel(self, batch_id: str) -> None:
        """Cancel a running batch.

        Args:
            batch_id: Batch ID from submit().
        """
        self._client.cancel_batch(batch_id)

    def estimate_cost(self, data: list[dict[str, Any]] | pl.DataFrame) -> CostEstimate:
        """Estimate cost without submitting.

        Args:
            data: Input rows as list of dicts or polars DataFrame.

        Returns:
            CostEstimate with token counts and cost breakdown.
        """
        rows = self._normalize_input(data)
        total_requests = len(rows)

        if total_requests == 0:
            return CostEstimate(
                cached_tokens=0,
                avg_input_tokens=0,
                estimated_output_tokens=0,
                total_requests=0,
                cache_write_cost=0.0,
                cache_read_cost=0.0,
                input_cost=0.0,
                output_cost=0.0,
                total_cost=0.0,
            )

        # Estimate tokens using 4 chars ≈ 1 token heuristic
        system_tokens = max(1, len(self.system_prompt) // 4)
        schema_tokens = max(1, len(json.dumps(self._json_schema)) // 4)
        cached_tokens = system_tokens + schema_tokens

        sample_prompt = self.template.format(**rows[0])
        avg_input_tokens = max(1, len(sample_prompt) // 4)

        num_fields = len(self.output_schema.model_fields)
        estimated_output_tokens = 50 * num_fields
        if self.reasoning:
            estimated_output_tokens += 100 * num_fields

        # Calculate costs
        pricing = MODEL_PRICING.get(self.model)
        if pricing is None:
            raise ClassifyError(f"Unknown model: {self.model}")

        cache_write_cost = (cached_tokens / 1_000_000) * pricing.cache_write_per_mtok
        cache_read_cost = (
            (cached_tokens / 1_000_000)
            * pricing.cache_read_per_mtok
            * (total_requests - 1)
            if total_requests > 1
            else 0.0
        )
        input_cost = (
            (avg_input_tokens / 1_000_000)
            * pricing.batch_input_per_mtok
            * total_requests
        )
        output_cost = (
            (estimated_output_tokens / 1_000_000)
            * pricing.batch_output_per_mtok
            * total_requests
        )
        total_cost = cache_write_cost + cache_read_cost + input_cost + output_cost

        return CostEstimate(
            cached_tokens=cached_tokens,
            avg_input_tokens=avg_input_tokens,
            estimated_output_tokens=estimated_output_tokens,
            total_requests=total_requests,
            cache_write_cost=cache_write_cost,
            cache_read_cost=cache_read_cost,
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=total_cost,
        )

    def _normalize_input(
        self, data: list[dict[str, Any]] | pl.DataFrame
    ) -> list[dict[str, str]]:
        """Convert input data to list of string-valued dicts."""
        if isinstance(data, pl.DataFrame):
            return [
                {col: str(row[col]) for col in self._columns}
                for row in data.iter_rows(named=True)
            ]
        if isinstance(data, list):
            return [{col: str(row[col]) for col in self._columns} for row in data]
        raise TypeError(f"Unsupported input type: {type(data)}")

    def _build_requests(self, rows: list[dict[str, str]]) -> list[dict[str, Any]]:
        """Build batch API request dicts in memory."""
        requests = []

        for idx, row in enumerate(rows):
            user_prompt = self.template.format(**row)

            messages: list[dict[str, Any]] = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": self.system_prompt,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                },
                {"role": "user", "content": user_prompt},
            ]

            requests.append(
                {
                    "custom_id": f"row_{idx}",
                    "params": {
                        "model": self.model,
                        "max_tokens": 4096,
                        "messages": messages,
                        "output_format": {
                            "type": "json_schema",
                            "schema": self._json_schema,
                        },
                    },
                }
            )

        return requests

    def _parse_results(self, raw_results: list[dict[str, Any]]) -> BatchResult[T]:
        """Parse raw API results into typed BatchResult."""
        results: list[tuple[int, T]] = []
        errors: list[RowError] = []

        for record in raw_results:
            custom_id = record.get("custom_id", "")
            row_idx = (
                int(custom_id.replace("row_", ""))
                if custom_id.startswith("row_")
                else 0
            )

            result = record.get("result")
            if not result:
                errors.append(
                    RowError(
                        row_index=row_idx,
                        error="No result in response",
                        raw_response=record,
                    )
                )
                continue

            if result.get("type") != "succeeded":
                error_msg = result.get("error", {}).get("message", "Unknown error")
                errors.append(
                    RowError(
                        row_index=row_idx,
                        error=error_msg,
                        raw_response=record,
                    )
                )
                continue

            message = result.get("message")
            if not message:
                errors.append(
                    RowError(
                        row_index=row_idx,
                        error="No message in result",
                        raw_response=record,
                    )
                )
                continue

            content = message.get("content", [])
            if not content:
                errors.append(
                    RowError(
                        row_index=row_idx,
                        error="Empty content in message",
                        raw_response=record,
                    )
                )
                continue

            text_content = content[0].get("text", "")
            try:
                data = json.loads(text_content)
                parsed = self.output_schema.model_validate(data)
                results.append((row_idx, parsed))
            except (json.JSONDecodeError, Exception) as e:
                errors.append(
                    RowError(
                        row_index=row_idx,
                        error=str(e),
                        raw_response=record,
                    )
                )

        return BatchResult(
            results=results,
            errors=errors,
            total=len(raw_results),
        )
