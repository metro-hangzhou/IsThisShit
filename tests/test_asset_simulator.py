from __future__ import annotations

from qq_data_integrations.napcat.asset_simulator import (
    default_forward_timeout_matrix,
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
