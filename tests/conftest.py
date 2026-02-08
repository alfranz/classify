"""Shared pytest configuration and fixtures."""

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests that hit the real Anthropic API",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if config.getoption("--run-integration"):
        return
    skip = pytest.mark.skip(reason="Need --run-integration flag to run")
    for item in items:
        if "test_integration" in str(item.fspath):
            item.add_marker(skip)
