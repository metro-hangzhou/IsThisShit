from __future__ import annotations

from qq_data_integrations.napcat.asset_simulator import (
    default_asset_resolution_scenarios,
    default_forward_timeout_matrix,
    run_asset_resolution_matrix,
    run_asset_resolution_scenario,
    run_forward_timeout_simulation,
)


def test_public_token_forward_video_same_parent_short_circuits_siblings() -> None:
    result = run_forward_timeout_simulation(
        route="public-token",
        asset_type="video",
        parents=1,
        siblings_per_parent=6,
        delay_s=0.0,
    )

    assert result.total_requests == 6
    assert result.backend_timeout_calls == 1
    assert result.short_circuited_requests == 5
    assert result.equivalent_live_timeout_s == result.timeout_budget_s


def test_public_token_forward_video_unique_parents_pay_one_timeout_each() -> None:
    result = run_forward_timeout_simulation(
        route="public-token",
        asset_type="video",
        parents=6,
        siblings_per_parent=1,
        delay_s=0.0,
    )

    assert result.total_requests == 6
    assert result.backend_timeout_calls == 6
    assert result.short_circuited_requests == 0
    assert result.equivalent_live_timeout_s == result.timeout_budget_s * 6


def test_forward_materialize_same_parent_short_circuits_siblings() -> None:
    result = run_forward_timeout_simulation(
        route="forward-materialize",
        asset_type="video",
        parents=1,
        siblings_per_parent=5,
        delay_s=0.0,
    )

    assert result.total_requests == 5
    assert result.backend_timeout_calls == 1
    assert result.short_circuited_requests == 4


def test_default_matrix_includes_video_and_speech_routes() -> None:
    results = default_forward_timeout_matrix(delay_s=0.0)

    assert len(results) >= 6
    assert any(item.route == "public-token" and item.asset_type == "video" for item in results)
    assert any(item.route == "forward-materialize" and item.asset_type == "video" for item in results)
    assert any(item.route == "public-token" and item.asset_type == "speech" for item in results)


def test_asset_resolution_matrix_matches_expectations() -> None:
    results = run_asset_resolution_matrix()

    assert len(results) >= 20
    assert all(item.matched for item in results)


def test_asset_resolution_matrix_includes_core_failure_and_remote_recovery_paths() -> None:
    results = {item.name: item for item in run_asset_resolution_matrix()}

    assert results["top_level_image_placeholder_zero_byte"].actual_resolver == "qq_not_downloaded_local_placeholder"
    assert results["top_level_image_placeholder_zero_byte"].actual_path_kind == "missing"

    assert results["top_level_speech_public_token_remote"].actual_resolver == "napcat_public_token_get_record_remote_url"
    assert results["top_level_speech_public_token_remote"].actual_path_kind == "remote"

    assert results["forward_old_video_public_token_timeout"].actual_resolver == "qq_expired_after_napcat"
    assert results["forward_old_video_public_token_timeout"].actual_path_kind == "missing"

    assert results["forward_old_video_materialize_timeout"].actual_resolver == "qq_expired_after_napcat"
    assert results["forward_old_video_materialize_timeout"].actual_path_kind == "missing"

    assert results["forward_video_relative_remote_url"].actual_resolver == "napcat_forward_remote_url"
    assert results["forward_video_relative_remote_url"].actual_path_kind == "remote"


def test_asset_resolution_case_reports_known_bad_video_token() -> None:
    scenario = {
        item.name: item
        for item in default_asset_resolution_scenarios()
    }["forward_video_known_bad_public_token"]

    result = run_asset_resolution_scenario(scenario)

    assert result.actual_resolver == "napcat_video_url_unavailable"
    assert result.actual_path_kind == "missing"
