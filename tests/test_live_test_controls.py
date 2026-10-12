"""Unit tests for explicit live-test selection, without connecting to Fusion."""

from unittest.mock import Mock

import pytest

from tests.conftest import pytest_addoption, pytest_collection_modifyitems


def test_live_options_are_explicit():
    parser = Mock()
    pytest_addoption(parser)
    assert parser.addoption.call_count == 3
    parser.addoption.assert_any_call(
        "--run-fusion-e2e", action="store_true", default=False
    )


def test_default_run_skips_only_live_items():
    config = Mock()
    config.getoption.return_value = False
    live = Mock()
    live.get_closest_marker.return_value = True
    unit = Mock()
    unit.get_closest_marker.return_value = None
    pytest_collection_modifyitems(config, [live, unit])
    live.add_marker.assert_called_once()
    unit.add_marker.assert_not_called()


def test_requested_live_run_does_not_skip():
    config = Mock()
    config.getoption.return_value = True
    live = Mock()
    pytest_collection_modifyitems(config, [live])
    live.add_marker.assert_not_called()


def test_requested_empty_live_selection_fails():
    config = Mock()
    config.getoption.return_value = True
    with pytest.raises(pytest.UsageError, match="no fusion_e2e tests selected"):
        pytest_collection_modifyitems(config, [])