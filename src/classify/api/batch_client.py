"""Claude Batch API client."""

import json
from pathlib import Path

from anthropic import Anthropic

from classify.core.models import BatchStatus


class BatchClient:
    """Client for Claude Batch API operations."""

    def __init__(self, api_key: str):
        """Initialize batch client.

        Args:
            api_key: Anthropic API key
        """
        self.client = Anthropic(
            api_key=api_key,
            default_headers={
                "anthropic-beta": "structured-outputs-2025-11-13,prompt-caching-2024-07-31"
            },
        )

    def create_batch(self, request_file_path: Path) -> str:
        """Create a new batch job.

        Args:
            request_file_path: Path to JSONL batch request file

        Returns:
            Batch ID
        """
        requests = []
        with open(request_file_path, "r") as f:
            for line in f:
                if line.strip():
                    requests.append(json.loads(line))

        batch = self.client.messages.batches.create(requests=requests)
        return batch.id

    def get_batch_status(self, batch_id: str) -> tuple[BatchStatus, dict]:
        """Get batch processing status.

        Args:
            batch_id: Batch ID

        Returns:
            Tuple of (status, batch_info_dict)
        """
        batch = self.client.messages.batches.retrieve(batch_id)

        status_mapping = {
            "in_progress": BatchStatus.IN_PROGRESS,
            "ended": BatchStatus.ENDED,
            "canceled": BatchStatus.CANCELED,
            "errored": BatchStatus.ERRORED,
        }

        status = status_mapping.get(batch.processing_status, BatchStatus.PENDING)

        info = {
            "request_counts": {
                "processing": batch.request_counts.processing,
                "succeeded": batch.request_counts.succeeded,
                "errored": batch.request_counts.errored,
                "canceled": batch.request_counts.canceled,
                "expired": batch.request_counts.expired,
            },
            "ended_at": batch.ended_at,
            "created_at": batch.created_at,
            "expires_at": batch.expires_at,
        }

        return status, info

    def download_results(self, batch_id: str, output_path: Path) -> None:
        """Download batch results.

        Args:
            batch_id: Batch ID
            output_path: Path to save results JSONL file
        """
        results = self.client.messages.batches.results(batch_id)

        with open(output_path, "w") as f:
            for result in results:
                f.write(result.model_dump_json() + "\n")

    def cancel_batch(self, batch_id: str) -> None:
        """Cancel a running batch.

        Args:
            batch_id: Batch ID
        """
        self.client.messages.batches.cancel(batch_id)

    def list_batches(self, limit: int = 20) -> list[dict]:
        """List recent batches.

        Args:
            limit: Maximum number of batches to return

        Returns:
            List of batch info dictionaries
        """
        batches = self.client.messages.batches.list(limit=limit)

        result = []
        for batch in batches.data:
            result.append(
                {
                    "id": batch.id,
                    "processing_status": batch.processing_status,
                    "created_at": batch.created_at,
                    "ended_at": batch.ended_at,
                    "request_counts": {
                        "processing": batch.request_counts.processing,
                        "succeeded": batch.request_counts.succeeded,
                        "errored": batch.request_counts.errored,
                    },
                }
            )

        return result
