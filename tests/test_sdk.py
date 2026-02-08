"""Tests for the classify Python SDK."""

import json
from typing import Literal
from unittest.mock import MagicMock, patch

import polars as pl
import pytest
from pydantic import BaseModel, Field

from classify.exceptions import ClassifyError, ClassifyTimeoutError
from classify.sdk import BatchInfo, Classifier


class Sentiment(BaseModel):
    sentiment: Literal["positive", "negative", "neutral"] = Field(
        description="The sentiment of the text"
    )
    confidence: float = Field(description="Confidence score from 0.0 to 1.0")


@pytest.fixture
def classifier():
    """Create a Classifier instance with mocked API key."""
    return Classifier(
        output_schema=Sentiment,
        system_prompt="You are a sentiment classifier.",
        template="Classify: {text}",
        model="claude-sonnet-4-5",
        api_key="test-key",
    )


class TestClassifierInit:
    def test_creates_with_valid_args(self) -> None:
        c = Classifier(
            output_schema=Sentiment,
            system_prompt="Classify.",
            template="Text: {text}",
            api_key="test-key",
        )
        assert c.model == "claude-sonnet-4-5"
        assert c.reasoning is False
        assert c.batch_size == 10_000

    def test_raises_without_api_key(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ClassifyError, match="API key required"):
                Classifier(
                    output_schema=Sentiment,
                    system_prompt="Classify.",
                    template="Text: {text}",
                )

    def test_infers_columns_from_template(self) -> None:
        c = Classifier(
            output_schema=Sentiment,
            system_prompt="Classify.",
            template="Title: {title}\nBody: {body}",
            api_key="test-key",
        )
        assert c._columns == ["title", "body"]

    def test_builds_json_schema(self) -> None:
        c = Classifier(
            output_schema=Sentiment,
            system_prompt="Classify.",
            template="Text: {text}",
            api_key="test-key",
        )
        schema = c._json_schema
        assert "properties" in schema
        assert "sentiment" in schema["properties"]
        assert "confidence" in schema["properties"]
        assert schema["additionalProperties"] is False

    def test_reasoning_adds_reasoning_fields_to_schema(self) -> None:
        c = Classifier(
            output_schema=Sentiment,
            system_prompt="Classify.",
            template="Text: {text}",
            api_key="test-key",
            reasoning=True,
        )
        schema = c._json_schema
        assert "sentiment_reasoning" in schema["properties"]
        assert "confidence_reasoning" in schema["properties"]


class TestNormalizeInput:
    def test_list_of_dicts(self, classifier: Classifier) -> None:
        data = [{"text": "Hello"}, {"text": "World"}]
        rows = classifier._normalize_input(data)
        assert rows == [{"text": "Hello"}, {"text": "World"}]

    def test_polars_dataframe(self, classifier: Classifier) -> None:
        df = pl.DataFrame({"text": ["Hello", "World"], "extra": [1, 2]})
        rows = classifier._normalize_input(df)
        assert rows == [{"text": "Hello"}, {"text": "World"}]

    def test_values_converted_to_strings(self, classifier: Classifier) -> None:
        data = [{"text": 42}]
        rows = classifier._normalize_input(data)
        assert rows == [{"text": "42"}]

    def test_unsupported_type_raises(self, classifier: Classifier) -> None:
        with pytest.raises(TypeError, match="Unsupported input type"):
            classifier._normalize_input("not a list or df")  # type: ignore[arg-type]


class TestBuildRequests:
    def test_request_structure(self, classifier: Classifier) -> None:
        rows = [{"text": "Hello"}]
        requests = classifier._build_requests(rows)

        assert len(requests) == 1
        req = requests[0]
        assert req["custom_id"] == "row_0"
        assert req["params"]["model"] == "claude-sonnet-4-5"
        assert req["params"]["max_tokens"] == 4096
        assert req["params"]["output_format"]["type"] == "json_schema"

    def test_messages_include_system_prompt_with_cache_control(
        self, classifier: Classifier
    ) -> None:
        rows = [{"text": "Hello"}]
        requests = classifier._build_requests(rows)
        messages = requests[0]["params"]["messages"]

        # First message has system prompt with cache_control
        assert messages[0]["role"] == "user"
        assert messages[0]["content"][0]["text"] == "You are a sentiment classifier."
        assert messages[0]["content"][0]["cache_control"] == {"type": "ephemeral"}

    def test_messages_include_user_prompt(self, classifier: Classifier) -> None:
        rows = [{"text": "Hello"}]
        requests = classifier._build_requests(rows)
        messages = requests[0]["params"]["messages"]

        # Second message is the rendered user prompt
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Classify: Hello"

    def test_multiple_rows_produce_multiple_requests(
        self, classifier: Classifier
    ) -> None:
        rows = [{"text": "A"}, {"text": "B"}, {"text": "C"}]
        requests = classifier._build_requests(rows)

        assert len(requests) == 3
        assert requests[0]["custom_id"] == "row_0"
        assert requests[1]["custom_id"] == "row_1"
        assert requests[2]["custom_id"] == "row_2"


class TestParseResults:
    def _make_success_result(
        self, row_idx: int, sentiment: str, confidence: float
    ) -> dict:
        return {
            "custom_id": f"row_{row_idx}",
            "result": {
                "type": "succeeded",
                "message": {
                    "content": [
                        {
                            "text": json.dumps(
                                {
                                    "sentiment": sentiment,
                                    "confidence": confidence,
                                }
                            )
                        }
                    ]
                },
            },
        }

    def _make_error_result(self, row_idx: int, error_msg: str) -> dict:
        return {
            "custom_id": f"row_{row_idx}",
            "result": {
                "type": "error",
                "error": {"message": error_msg},
            },
        }

    def test_parse_successful_results(self, classifier: Classifier) -> None:
        raw = [
            self._make_success_result(0, "positive", 0.95),
            self._make_success_result(1, "negative", 0.8),
        ]
        result = classifier._parse_results(raw)

        assert result.success_count == 2
        assert result.error_count == 0
        assert result.total == 2

        items = result.to_list()
        assert items[0].sentiment == "positive"
        assert items[0].confidence == 0.95
        assert items[1].sentiment == "negative"
        assert items[1].confidence == 0.8

    def test_parse_error_results(self, classifier: Classifier) -> None:
        raw = [self._make_error_result(0, "Rate limit exceeded")]
        result = classifier._parse_results(raw)

        assert result.success_count == 0
        assert result.error_count == 1
        assert result.errors[0].error == "Rate limit exceeded"

    def test_parse_mixed_results(self, classifier: Classifier) -> None:
        raw = [
            self._make_success_result(0, "positive", 0.9),
            self._make_error_result(1, "Failed"),
        ]
        result = classifier._parse_results(raw)

        assert result.success_count == 1
        assert result.error_count == 1

    def test_to_list_raises_on_errors(self, classifier: Classifier) -> None:
        raw = [
            self._make_success_result(0, "positive", 0.9),
            self._make_error_result(1, "Failed"),
        ]
        result = classifier._parse_results(raw)

        with pytest.raises(ClassifyError, match="1 row\\(s\\) failed"):
            result.to_list()

    def test_results_ordered_by_row_index(self, classifier: Classifier) -> None:
        raw = [
            self._make_success_result(2, "neutral", 0.5),
            self._make_success_result(0, "positive", 0.9),
            self._make_success_result(1, "negative", 0.8),
        ]
        result = classifier._parse_results(raw)
        items = result.to_list()

        assert items[0].sentiment == "positive"
        assert items[1].sentiment == "negative"
        assert items[2].sentiment == "neutral"

    def test_to_dataframe(self, classifier: Classifier) -> None:
        raw = [
            self._make_success_result(1, "negative", 0.8),
            self._make_success_result(0, "positive", 0.9),
        ]
        result = classifier._parse_results(raw)
        df = result.to_dataframe()

        assert df.shape == (2, 2)
        assert df.columns == ["sentiment", "confidence"]
        assert df["sentiment"].to_list() == ["positive", "negative"]
        assert df["confidence"].to_list() == [0.9, 0.8]

    def test_to_dataframe_raises_on_errors(self, classifier: Classifier) -> None:
        raw = [self._make_error_result(0, "Failed")]
        result = classifier._parse_results(raw)

        with pytest.raises(ClassifyError):
            result.to_dataframe()

    def test_reasoning_fields_ignored_by_pydantic(self, classifier: Classifier) -> None:
        """Reasoning fields in API response are silently dropped by Pydantic."""
        raw = [
            {
                "custom_id": "row_0",
                "result": {
                    "type": "succeeded",
                    "message": {
                        "content": [
                            {
                                "text": json.dumps(
                                    {
                                        "sentiment": "positive",
                                        "confidence": 0.9,
                                        "sentiment_reasoning": "Very enthusiastic language",
                                        "confidence_reasoning": "Clear sentiment",
                                    }
                                )
                            }
                        ]
                    },
                },
            }
        ]
        result = classifier._parse_results(raw)
        item = result.to_list()[0]
        assert item.sentiment == "positive"
        assert not hasattr(item, "sentiment_reasoning")


class TestBatchInfo:
    def test_is_done_for_ended(self) -> None:
        info = BatchInfo(
            batch_id="x", status="ended", total=10, succeeded=10, errored=0
        )
        assert info.is_done is True

    def test_is_done_for_in_progress(self) -> None:
        info = BatchInfo(
            batch_id="x", status="in_progress", total=10, succeeded=5, errored=0
        )
        assert info.is_done is False

    def test_progress_calculation(self) -> None:
        info = BatchInfo(
            batch_id="x", status="in_progress", total=10, succeeded=5, errored=1
        )
        assert info.progress == pytest.approx(0.6)


class TestEstimateCost:
    def test_returns_cost_estimate(self, classifier: Classifier) -> None:
        data = [{"text": "Hello"}, {"text": "World"}]
        estimate = classifier.estimate_cost(data)

        assert estimate.total_requests == 2
        assert estimate.cached_tokens > 0
        assert estimate.avg_input_tokens > 0
        assert estimate.total_cost > 0

    def test_empty_data_returns_zero_cost(self, classifier: Classifier) -> None:
        estimate = classifier.estimate_cost([])
        assert estimate.total_requests == 0
        assert estimate.total_cost == 0.0

    def test_unknown_model_raises(self) -> None:
        c = Classifier(
            output_schema=Sentiment,
            system_prompt="Classify.",
            template="Text: {text}",
            api_key="test-key",
            model="unknown-model",
        )
        with pytest.raises(ClassifyError, match="Unknown model"):
            c.estimate_cost([{"text": "Hello"}])


class TestSubmit:
    def test_submit_calls_batch_client(self, classifier: Classifier) -> None:
        classifier._client = MagicMock()
        classifier._client.create_batch_from_requests.return_value = "batch_123"

        batch_id = classifier.submit([{"text": "Hello"}])

        assert batch_id == "batch_123"
        classifier._client.create_batch_from_requests.assert_called_once()

    def test_submit_with_dataframe(self, classifier: Classifier) -> None:
        classifier._client = MagicMock()
        classifier._client.create_batch_from_requests.return_value = "batch_456"

        df = pl.DataFrame({"text": ["Hello", "World"]})
        batch_id = classifier.submit(df)

        assert batch_id == "batch_456"
        args = classifier._client.create_batch_from_requests.call_args
        assert len(args[0][0]) == 2


class TestClassify:
    def test_classify_polls_and_returns_results(self, classifier: Classifier) -> None:
        mock_client = MagicMock()
        classifier._client = mock_client

        mock_client.create_batch_from_requests.return_value = "batch_1"

        # First status check: in_progress, second: ended
        from classify.core.models import BatchStatus

        mock_client.get_batch_status.side_effect = [
            (
                BatchStatus.IN_PROGRESS,
                {
                    "request_counts": {
                        "succeeded": 0,
                        "errored": 0,
                        "processing": 1,
                        "canceled": 0,
                        "expired": 0,
                    }
                },
            ),
            (
                BatchStatus.ENDED,
                {
                    "request_counts": {
                        "succeeded": 1,
                        "errored": 0,
                        "processing": 0,
                        "canceled": 0,
                        "expired": 0,
                    }
                },
            ),
        ]

        mock_client.get_results_as_dicts.return_value = [
            {
                "custom_id": "row_0",
                "result": {
                    "type": "succeeded",
                    "message": {
                        "content": [
                            {
                                "text": json.dumps(
                                    {"sentiment": "positive", "confidence": 0.95}
                                )
                            }
                        ]
                    },
                },
            }
        ]

        results = classifier.classify([{"text": "Great!"}], poll_interval=0.01)

        assert len(results) == 1
        assert results[0].sentiment == "positive"

    def test_classify_raises_on_timeout(self, classifier: Classifier) -> None:
        mock_client = MagicMock()
        classifier._client = mock_client

        mock_client.create_batch_from_requests.return_value = "batch_1"

        from classify.core.models import BatchStatus

        mock_client.get_batch_status.return_value = (
            BatchStatus.IN_PROGRESS,
            {
                "request_counts": {
                    "succeeded": 0,
                    "errored": 0,
                    "processing": 1,
                    "canceled": 0,
                    "expired": 0,
                }
            },
        )

        with pytest.raises(ClassifyTimeoutError, match="did not complete"):
            classifier.classify([{"text": "Hello"}], poll_interval=0.01, timeout=0.02)
