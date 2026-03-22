from __future__ import annotations

from qq_data_integrations.napcat.asset_simulator import (
    all_asset_resolution_scenarios,
    default_asset_resolution_scenarios,
    default_forward_timeout_matrix,
    run_asset_resolution_matrix,
    run_asset_resolution_sequence,
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

    assert len(results) >= 450
    assert all(item.matched for item in results)


def test_asset_resolution_matrix_includes_core_failure_and_remote_recovery_paths() -> None:
    results = {item.name: item for item in run_asset_resolution_matrix()}

    assert results["top_level_image_placeholder_zero_byte"].actual_resolver == "qq_not_downloaded_local_placeholder"
    assert results["top_level_image_placeholder_zero_byte"].actual_path_kind == "missing"

    assert results["top_level_speech_public_token_remote"].actual_resolver == "napcat_public_token_get_record_remote_url"
    assert results["top_level_speech_public_token_remote"].actual_path_kind == "remote"
    assert results["top_level_sticker_relative_remote_gif"].actual_resolver == "sticker_remote_download"
    assert results["top_level_sticker_relative_remote_gif"].actual_path_kind == "remote"

    assert results["forward_old_video_public_token_timeout"].actual_resolver == "qq_expired_after_napcat"
    assert results["forward_old_video_public_token_timeout"].actual_path_kind == "missing"

    assert results["forward_old_video_materialize_timeout"].actual_resolver == "qq_expired_after_napcat"
    assert results["forward_old_video_materialize_timeout"].actual_path_kind == "missing"
    assert results["forward_old_video_materialize_timeout"].cost_matched is True

    assert results["forward_video_relative_remote_url"].actual_resolver == "napcat_forward_remote_url"
    assert results["forward_video_relative_remote_url"].actual_path_kind == "remote"

    assert results["forward_old_video_route_unavailable"].actual_resolver == "qq_expired_after_napcat"
    assert results["forward_old_video_route_unavailable"].actual_path_kind == "missing"
    assert results["forward_video_missing_parent_element_id"].actual_resolver is None
    assert results["forward_video_missing_parent_element_id"].actual_path_kind == "missing"
    assert results["forward_video_stale_path_live_remote_url"].actual_resolver == "napcat_forward_remote_url"
    assert results["forward_video_stale_path_live_remote_url"].actual_path_kind == "remote"
    assert results["nested_forward_video_missing_peer_uid_live_http"].actual_resolver == "napcat_forward_remote_url"
    assert results["nested_forward_video_missing_peer_uid_live_http"].actual_path_kind == "remote"
    assert results["forward_video_very_old_empty_terminal"].actual_resolver == "qq_expired_after_napcat"
    assert results["forward_video_very_old_empty_terminal"].actual_path_kind == "missing"
    assert results["forward_video_very_old_materialize_error"].actual_resolver == "qq_expired_after_napcat"
    assert results["forward_video_very_old_materialize_error"].actual_path_kind == "missing"
    assert results["forward_video_very_old_public_not_found"].actual_resolver == "qq_expired_after_napcat"
    assert results["forward_video_very_old_public_not_found"].actual_path_kind == "missing"
    assert results["forward_video_very_old_direct_not_found"].actual_resolver == "qq_expired_after_napcat"
    assert results["forward_video_very_old_direct_not_found"].actual_path_kind == "missing"
    assert results["nested_forward_speech_very_old_timeout"].actual_resolver == "qq_expired_after_napcat"
    assert results["nested_forward_speech_very_old_timeout"].actual_path_kind == "missing"
    assert results["nested_forward_speech_very_old_materialize_error"].actual_resolver == "qq_expired_after_napcat"
    assert results["nested_forward_speech_very_old_materialize_error"].actual_path_kind == "missing"
    assert results["nested_forward_file_recent_relative_http_remote_recovery"].actual_resolver == "napcat_forward_remote_url"
    assert results["nested_forward_file_recent_relative_http_remote_recovery"].actual_path_kind == "remote"
    assert results["nested_forward_sticker_relative_http_remote_recovery"].actual_resolver == "sticker_remote_download"
    assert results["nested_forward_sticker_relative_http_remote_recovery"].actual_path_kind == "remote"
    assert results["forward_sticker_missing_peer_uid_live_http"].actual_resolver == "sticker_remote_download"
    assert results["forward_sticker_missing_peer_uid_live_http"].actual_path_kind == "remote"


def test_asset_resolution_case_reports_known_bad_video_token() -> None:
    scenario = {
        item.name: item
        for item in default_asset_resolution_scenarios()
    }["forward_video_known_bad_public_token"]

    result = run_asset_resolution_scenario(scenario)

    assert result.actual_resolver == "napcat_video_url_unavailable"
    assert result.actual_path_kind == "missing"


def test_asset_resolution_matrix_can_filter_by_suite() -> None:
    route_health = run_asset_resolution_matrix(suite="route_health")
    suites = {item.suite for item in route_health}

    assert route_health
    assert suites == {"route_health"}


def test_asset_resolution_scenario_catalog_is_systematic() -> None:
    scenarios = all_asset_resolution_scenarios()
    names = {item.name for item in scenarios}

    assert len(scenarios) >= 384
    assert len(names) == len(scenarios)
    assert any(item.topology == "nested_forward" for item in scenarios)
    assert any(item.suite == "family_diff_matrix" for item in scenarios)
    assert any(item.suite == "exhaustive_old_forward_terminal" for item in scenarios)
    assert any(item.suite == "exhaustive_sticker_forward_parent" for item in scenarios)
    assert any(item.suite == "exhaustive_local_path_states" for item in scenarios)
    assert any(item.suite == "exhaustive_old_forward_direct_file_id" for item in scenarios)
    assert any(item.suite == "public_token_shape_drift" for item in scenarios)
    assert any(item.suite == "exhaustive_old_forward_payload_file_id" for item in scenarios)
    assert any(item.suite == "exhaustive_old_public_zero_byte" for item in scenarios)
    assert any("public_not_found" in item.name for item in scenarios)
    assert any("direct_not_found" in item.name for item in scenarios)
    assert any(item.asset_type == "sticker" and item.topology == "nested_forward" for item in scenarios)


def test_asset_resolution_exhaustive_old_forward_terminal_suite_matches_expectations() -> None:
    results = run_asset_resolution_matrix(suite="exhaustive_old_forward_terminal")

    assert len(results) == 144
    assert all(item.matched for item in results)
    assert all(item.actual_resolver == "qq_expired_after_napcat" for item in results)
    assert all(item.actual_path_kind == "missing" for item in results)


def test_asset_resolution_exhaustive_sticker_forward_parent_suite_matches_expectations() -> None:
    results = run_asset_resolution_matrix(suite="exhaustive_sticker_forward_parent")

    assert len(results) == 24
    assert all(item.matched for item in results)
    assert any(item.actual_resolver == "sticker_remote_download" for item in results)
    assert any(item.actual_resolver is None for item in results)


def test_asset_resolution_exhaustive_local_path_state_suite_matches_expectations() -> None:
    results = run_asset_resolution_matrix(suite="exhaustive_local_path_states")

    assert len(results) == 25
    assert all(item.matched for item in results)
    assert any(item.actual_resolver == "source_local_path" for item in results)
    assert any(item.actual_resolver == "hint_local_path" for item in results)


def test_asset_resolution_exhaustive_old_forward_direct_file_id_suite_matches_expectations() -> None:
    results = run_asset_resolution_matrix(suite="exhaustive_old_forward_direct_file_id")

    assert len(results) == 36
    assert all(item.matched for item in results)
    assert all(item.actual_resolver == "qq_expired_after_napcat" for item in results)
    assert all(item.actual_path_kind == "missing" for item in results)


def test_asset_resolution_public_token_shape_drift_suite_matches_expectations() -> None:
    results = run_asset_resolution_matrix(suite="public_token_shape_drift")

    assert len(results) == 36
    assert all(item.matched for item in results)
    assert any(item.actual_path_kind == "local" for item in results)
    assert any(item.actual_path_kind == "remote" for item in results)


def test_asset_resolution_old_forward_payload_file_id_suite_matches_expectations() -> None:
    results = run_asset_resolution_matrix(suite="exhaustive_old_forward_payload_file_id")

    assert len(results) == 36
    assert all(item.matched for item in results)
    assert all(item.actual_resolver == "qq_expired_after_napcat" for item in results)
    assert all(item.actual_path_kind == "missing" for item in results)


def test_asset_resolution_old_public_zero_byte_suite_matches_expectations() -> None:
    results = run_asset_resolution_matrix(suite="exhaustive_old_public_zero_byte")

    assert len(results) == 18
    assert all(item.matched for item in results)
    assert all(item.actual_resolver == "qq_expired_after_napcat" for item in results)
    assert all(item.actual_path_kind == "missing" for item in results)


def test_asset_resolution_sequence_reuses_old_forward_timeout_classification() -> None:
    scenario = {
        item.name: item
        for item in all_asset_resolution_scenarios()
    }["forward_old_video_public_token_timeout"]

    result = run_asset_resolution_sequence(scenario, repeats=3)

    assert result.matched is True
    assert result.actual_resolver == "qq_expired_after_napcat"
    assert result.actual_path_kind == "missing"
    assert result.client_call_count == 1
    assert result.fast_call_count == 1
    assert result.remote_attempt_count == 0


def test_asset_resolution_sequence_reuses_route_unavailable_fast_fail() -> None:
    scenario = {
        item.name: item
        for item in all_asset_resolution_scenarios()
    }["forward_old_video_route_unavailable"]

    result = run_asset_resolution_sequence(scenario, repeats=3)

    assert result.matched is True
    assert result.actual_resolver == "qq_expired_after_napcat"
    assert result.actual_path_kind == "missing"
    assert result.client_call_count == 0
    assert result.fast_call_count == 1
    assert result.remote_attempt_count == 0


def test_asset_resolution_sequence_reuses_public_token_shape_drift_success() -> None:
    scenario = {
        item.name: item
        for item in all_asset_resolution_scenarios()
    }["public_token_shape_drift_forward_video_valid_remote"]

    result = run_asset_resolution_sequence(scenario, repeats=3)

    assert result.matched is True
    assert result.actual_resolver == "napcat_public_token_get_file_remote_url"
    assert result.actual_path_kind == "remote"
    assert result.client_call_count == 2
    assert result.fast_call_count == 1
    assert result.remote_attempt_count == 1


def test_asset_resolution_sequence_reuses_public_token_remote_url_only_success() -> None:
    scenario = {
        item.name: item
        for item in all_asset_resolution_scenarios()
    }["public_token_shape_drift_forward_video_valid_remote_only"]

    result = run_asset_resolution_sequence(scenario, repeats=3)

    assert result.matched is True
    assert result.actual_resolver == "napcat_public_token_get_file_remote_url"
    assert result.actual_path_kind == "remote"
    assert result.client_call_count == 2
    assert result.fast_call_count == 1
    assert result.remote_attempt_count == 1


def test_asset_resolution_sequence_reuses_payload_only_direct_file_id_fast_fail() -> None:
    scenario = {
        item.name: item
        for item in all_asset_resolution_scenarios()
    }["exhaustive_forward_video_stale_missing_blank_payload_payload_file_id"]

    result = run_asset_resolution_sequence(scenario, repeats=3)

    assert result.matched is True
    assert result.actual_resolver == "qq_expired_after_napcat"
    assert result.actual_path_kind == "missing"
    assert result.client_call_count == 1
    assert result.fast_call_count == 1
    assert result.remote_attempt_count == 0
