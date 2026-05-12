# 测试矩阵

这份文件把当前 `tests/` 面分成 active domains。

## Analysis / Benshi

- `test_analysis_docs.py`
- `test_analysis_service.py`
- `test_benshi_llm_agent.py`
- `test_benshi_master_agent.py`
- `test_benshi_posterior.py`
- `test_judgment_policy.py`
- `test_benshi_seed_artifacts.py`
- `test_llm_analysis.py`
- `test_llm_window_analysis.py`
- `test_full_chain_profile_warnings.py`
- `test_review_packets.py`
- `test_review_service.py`

## Preprocess

- `test_chunk_policies.py`
- `test_embedding_env.py`
- `test_embedding_policy.py`
- `test_preprocess_adapters.py`
- `test_preprocess_detect.py`
- `test_preprocess_docs.py`
- `test_preprocess_identities.py`
- `test_preprocess_service.py`
- `test_rag_retrieval.py`
- `test_runtime_control.py`

## Exporter / NapCat

- `test_asset_simulator.py`
- `test_export_perf.py`
- `test_export_selection_summary.py`
- `test_media_bundle_recent_identity_reuse.py`
- `test_media_downloader_progress_and_forward_timeout.py`
- `test_napcat_bootstrap.py`
- `test_napcat_provider_boundary_and_forward.py`
- `test_napcat_quick_login.py`
- `test_napcat_runtime_diagnostics.py`
- `test_napcat_settings.py`
- `test_normalize_forward_detail.py`
- `test_sticker_asset_coverage.py`
- `test_targeted_missing_retest.py`

## CLI / Runtime

- `test_cli_app_login.py`
- `test_cli_login_completion.py`
- `test_cli_status_display.py`
- `test_repl_login.py`
- `test_restart_napcat_service.py`
- `test_start_cli_script.py`
- `test_start_napcat_logged.py`
- `test_watch_view.py`

## Local Corpus / Workbench

- `test_local_corpora_integrity.py`
- `test_local_testdata_corpora.py`
- `test_probe_asset_routes_script.py`
- `test_program_workbench_contract.py`

## 历史测试面

那些当前 worktree 里不在 active surface 的旧 tracked tests，都已经保留在 tests archive。

这意味着：

- 现在不要把它们当成丢了
- 也不要把它们误当成当前 active baseline
