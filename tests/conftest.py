"""Explicit opt-in for local, read-only Fusion acceptance tests."""

import pytest


def pytest_addoption(parser):
    parser.addoption("--run-fusion-e2e", action="store_true", default=False)
    parser.addoption("--fusion-test-body", default=None)
    parser.addoption("--fusion-test-component", default=None)


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config, items):
    live = [item for item in items if item.get_closest_marker("fusion_e2e")]
    if config.getoption("--run-fusion-e2e"):
        if not live:
            raise pytest.UsageError(
                "Live acceptance requested but no fusion_e2e tests selected"
            )
        return
    for item in live:
        item.add_marker(
            pytest.mark.skip(reason="Live Fusion requires --run-fusion-e2e")
        )