"""classify - LLM-based classification on CSV data using Claude's Batch API."""

__version__ = "0.1.0"

from classify.sdk import BatchInfo, BatchResult, Classifier, RowError

__all__ = ["Classifier", "BatchInfo", "BatchResult", "RowError"]
