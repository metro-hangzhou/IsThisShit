from __future__ import annotations

import os
from pathlib import Path
from time import monotonic

import typer

from qq_data_cli.logging_utils import get_cli_log_path, get_cli_logger, setup_cli_logging
from qq_data_cli.export_cleanup import cleanup_gateway_media_cache
from qq_data_cli.qr import render_qr_text
from qq_data_cli.repl import SlashRepl
from qq_data_cli.startup_capture import capture_startup_snapshot, get_session_startup_capture_path
from qq_data_cli.terminal_compat import (
    apply_cli_ui_mode_override,
    probe_terminal_environment,
    read_requested_cli_ui_mode,
    render_terminal_doctor_lines,
    resolve_cli_ui_mode,
)
from qq_data_core import (
    ChatExportService,
    ExportForensicsCollector,
    ExportPerfTraceWriter,
    resolve_strict_missing_policy,
    ExportRequest,
    build_export_content_summary,
    build_default_output_path,
    format_missing_breakdown_compact,
)
from qq_data_integrations import FixtureSnapshotLoader, discover_qq_media_roots
from qq_data_integrations.napcat import (
    NapCatBootstrapper,
    ChatTarget,
    collect_debug_preflight_evidence,
    NapCatGateway,
    NapCatQrLoginService,
    NapCatSettings,
    NapCatTargetLookupError,
    NapCatWebUiClient,
)

app = typer.Typer(
    help="QQ chat exporter developer CLI",
    invoke_without_command=True,
    no_args_is_help=False,
)

CLI_HISTORY_SINGLE_PAGE_LIMIT = 200


def _init_cli_logging() -> NapCatSettings:
    settings = NapCatSettings.from_env()
    log_path = setup_cli_logging(settings.state_dir)
    get_cli_logger("app").info(
        "cli_entry state_dir=%s project_root=%s log_path=%s",
        settings.state_dir,
        settings.project_root,
        log_path,
    )
    return settings


@app.callback(invoke_without_command=True)
def cli(
    ctx: typer.Context,
    ui: str | None = typer.Option(
        None,
        "--ui",
        help="CLI 显示模式：auto、full、compat。",
    ),
) -> None:
    settings = _init_cli_logging()
    try:
        apply_cli_ui_mode_override(ui)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    terminal_probe = probe_terminal_environment()
    ui_decision = resolve_cli_ui_mode(
        terminal_probe,
        requested_mode=read_requested_cli_ui_mode(),
    )
    startup_capture_path = capture_startup_snapshot(
        settings,
        terminal_probe=terminal_probe,
        ui_decision=ui_decision,
    )
    if startup_capture_path is not None:
        get_cli_logger("app").info("startup_capture_path=%s", startup_capture_path)
    if ctx.invoked_subcommand is None:
        SlashRepl(
            terminal_probe=terminal_probe,
            ui_decision=ui_decision,
            startup_capture_path=startup_capture_path,
        ).run()


@app.command()
def shell() -> None:
    _init_cli_logging()
    SlashRepl(startup_capture_path=get_session_startup_capture_path()).run()


@app.command("terminal-doctor")
def terminal_doctor() -> None:
    _init_cli_logging()
    probe = probe_terminal_environment()
    decision = resolve_cli_ui_mode(
        probe,
        requested_mode=read_requested_cli_ui_mode(),
    )
    typer.echo("\n".join(render_terminal_doctor_lines(probe, decision)))


@app.command()
def login(
    timeout: float = typer.Option(300.0, "--timeout"),
    poll: float = typer.Option(3.0, "--poll"),
    refresh: bool = typer.Option(False, "--refresh"),
    webui_url: str | None = typer.Option(None, "--webui-url"),
    webui_token: str | None = typer.Option(None, "--webui-token"),
) -> None:
    base_settings = NapCatSettings.from_env()
    settings = base_settings.model_copy(
        update={
            "webui_url": webui_url or base_settings.webui_url,
            "webui_token": webui_token if webui_token is not None else base_settings.webui_token,
        }
    )
    start_result = NapCatBootstrapper(settings).ensure_endpoint("webui")
    if not start_result.ready:
        raise typer.BadParameter(start_result.message)
    if (start_result.attempted_start or start_result.attempted_configure) and start_result.message:
        typer.echo(start_result.message)
        refreshed_settings = NapCatSettings.from_env()
        settings = refreshed_settings.model_copy(
            update={
                "webui_url": webui_url or refreshed_settings.webui_url,
                "webui_token": webui_token if webui_token is not None else refreshed_settings.webui_token,
            }
        )
    client = NapCatWebUiClient(
        settings.webui_url,
        raw_token=settings.webui_token,
        use_system_proxy=settings.use_system_proxy,
    )
    try:
        service = NapCatQrLoginService(client)

        def on_qr(url: str) -> None:
            typer.echo(render_qr_text(url))
            typer.echo(f"qr_url={url}")

        def on_status(status) -> None:
            if status.login_error:
                typer.echo(f"login_status={status.login_error}")

        info = service.login_until_success(
            timeout_seconds=timeout,
            poll_interval=poll,
            refresh=refresh,
            on_qrcode=on_qr,
            on_status=on_status,
        )
        typer.echo("QQ login succeeded.")
        typer.echo(f"uin={info.uin or ''}")
        typer.echo(f"nick={info.nick or ''}")
        typer.echo(f"online={info.online}")
    finally:
        client.close()


@app.command("export-fixture")
def export_fixture(
    fixture_path: Path,
    out_path: Path,
    fmt: str = typer.Option("jsonl", "--format", "-f"),
) -> None:
    loader = FixtureSnapshotLoader()
    service = ChatExportService()
    media_roots = discover_qq_media_roots()
    snapshot = loader.load_export(fixture_path)
    normalized = service.build_snapshot(snapshot)
    bundle = service.write_bundle(
        normalized,
        out_path,
        fmt=fmt.lower(),
        media_search_roots=media_roots,
        media_cache_dir=Path("state") / "media_index",
    )
    typer.echo(str(bundle.data_path))


@app.command("export-history")
def export_history(
    chat_type: str,
    chat_ref: str,
    out_path: Path | None = typer.Option(None, "--out"),
    fmt: str = typer.Option("jsonl", "--format", "-f"),
    chat_name: str | None = typer.Option(None, "--chat-name"),
    http_url: str | None = typer.Option(None, "--http-url"),
    access_token: str | None = typer.Option(None, "--token"),
    limit: int = typer.Option(20, "--limit"),
    output_dir: Path | None = typer.Option(None, "--output-dir"),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
    refresh: bool = typer.Option(False, "--refresh"),
    strict_missing: str | None = typer.Option(
        None,
        "--strict-missing",
        help="调试导出缺失策略：off、collect、abort、threshold:N。",
    ),
) -> None:
    logger = get_cli_logger("app")
    normalized_chat_type = "group" if chat_type.lower() == "group" else "private"
    base_settings = NapCatSettings.from_env()
    settings = base_settings.model_copy(
        update={
            "http_url": http_url or base_settings.http_url,
            "access_token": access_token if access_token is not None else base_settings.access_token,
            "export_dir": output_dir or base_settings.export_dir,
            "state_dir": state_dir or base_settings.state_dir,
        }
    )
    start_result = NapCatBootstrapper(settings).ensure_endpoint("onebot_http")
    if not start_result.ready:
        raise typer.BadParameter(start_result.message)
    if start_result.attempted_start or start_result.attempted_configure:
        refreshed_settings = NapCatSettings.from_env()
        settings = refreshed_settings.model_copy(
            update={
                "http_url": http_url or refreshed_settings.http_url,
                "access_token": access_token if access_token is not None else refreshed_settings.access_token,
                "export_dir": output_dir or refreshed_settings.export_dir,
                "state_dir": state_dir or refreshed_settings.state_dir,
            }
        )
    gateway = NapCatGateway(settings)
    trace = None
    forensics = None
    try:
        target = _resolve_target(gateway, normalized_chat_type, chat_ref, chat_name=chat_name, refresh=refresh)
        trace = ExportPerfTraceWriter(
            settings.state_dir,
            chat_type=normalized_chat_type,
            chat_id=target.chat_id,
            mode="cli_export",
        )
        progress_callback = _build_cli_export_progress_callback(trace)
        forensics = ExportForensicsCollector(
            settings.state_dir,
            chat_type=normalized_chat_type,
            chat_id=target.chat_id,
            policy=resolve_strict_missing_policy(strict_missing, env=os.environ),
            command_context={
                "entrypoint": "app.export-history",
                "format": fmt.lower(),
                "limit": limit,
                "strict_missing": strict_missing,
                "chat_ref": chat_ref,
                "chat_name": chat_name or target.display_name,
            },
        )
        forensics.capture_preflight(
            {
                "http_url": settings.http_url,
                "fast_history_mode": settings.fast_history_mode,
                "fast_history_url": settings.fast_history_url,
                "export_dir": str(settings.export_dir),
                "state_dir": str(settings.state_dir),
                "project_root": str(settings.project_root),
                **collect_debug_preflight_evidence(settings),
            }
        )
        trace.write_event(
            "export_start",
            {
                "chat_name": target.display_name,
                "format": fmt.lower(),
                "limit": limit,
                "target_dir": str((out_path.parent if out_path is not None else settings.export_dir).resolve()),
            },
        )
        request = ExportRequest(
            chat_type=normalized_chat_type,
            chat_id=target.chat_id,
            chat_name=chat_name or target.display_name,
            limit=limit,
        )
        history_page_size = max(100, min(limit, 500))
        if limit > CLI_HISTORY_SINGLE_PAGE_LIMIT:
            source_snapshot = gateway.fetch_snapshot_tail(
                request,
                data_count=limit,
                page_size=history_page_size,
                progress_callback=progress_callback,
            )
        else:
            source_snapshot = gateway.fetch_snapshot(request)
        service = ChatExportService()
        normalized = service.build_snapshot(source_snapshot)
        target_path = out_path or build_default_output_path(
            settings.export_dir,
            chat_type=normalized_chat_type,
            chat_id=target.chat_id,
            fmt=fmt.lower(),
        )
        bundle = service.write_bundle(
            normalized,
            target_path,
            fmt=fmt.lower(),
            media_resolution_mode="napcat_only",
            media_download_manager=(
                gateway.build_media_download_manager()
                if hasattr(gateway, "build_media_download_manager")
                else None
            ),
            progress_callback=progress_callback,
            forensics_collector=forensics,
        )
        cleanup_stats = cleanup_gateway_media_cache(gateway, trace=trace, logger=logger)
        content_summary = build_export_content_summary(normalized, bundle, profile="all")
        summary = trace.build_summary(record_count=len(normalized.messages))
        trace.write_event(
            "export_complete",
            {
                "out_path": str(bundle.data_path.resolve()),
                "manifest_path": str(bundle.manifest_path.resolve()),
                "copied_asset_count": bundle.copied_asset_count,
                "reused_asset_count": bundle.reused_asset_count,
                "missing_asset_count": bundle.missing_asset_count,
                "remote_cache_cleanup": cleanup_stats,
                "content_summary": content_summary,
                **summary,
            },
        )
        forensic_summary_path = (
            forensics.finalize(
                export_completed=True,
                aborted=False,
                data_path=bundle.data_path,
                manifest_path=bundle.manifest_path,
                trace_path=trace.path,
                log_path=get_cli_log_path(),
            )
            if forensics is not None and forensics.enabled
            else None
        )
        if forensic_summary_path is not None:
            bundle.forensic_summary_path = forensic_summary_path
            bundle.forensic_run_dir = forensic_summary_path.parent
            bundle.forensic_incident_count = forensics.incident_count
        trace.close()
        typer.echo(str(bundle.data_path))
        missing_kinds = format_missing_breakdown_compact(content_summary)
        typer.echo(
            (
                f"records={len(normalized.messages)} copied={bundle.copied_asset_count} "
                f"reused={bundle.reused_asset_count} missing={bundle.missing_asset_count} "
                f"missing_kinds=[{missing_kinds}] "
                f"pages={summary['pages_scanned']} retries={summary['retry_events']} trace={trace.path}"
            ),
            err=True,
        )
        if int(getattr(bundle, "forensic_incident_count", 0) or 0):
            typer.echo(
                f"forensics: incidents={getattr(bundle, 'forensic_incident_count', 0)} "
                f"summary={getattr(bundle, 'forensic_summary_path', None)}",
                err=True,
            )
            typer.echo(
                "send_back: "
                f"manifest={bundle.manifest_path} "
                f"trace={trace.path} "
                f"forensic_summary={getattr(bundle, 'forensic_summary_path', None)} "
                f"log={get_cli_log_path()}",
                err=True,
            )
    except Exception as exc:
        if trace is not None:
            cleanup_stats = cleanup_gateway_media_cache(gateway, trace=trace, logger=logger)
            trace.write_event(
                "export_failed",
                {
                    "error": str(exc),
                    "remote_cache_cleanup": cleanup_stats,
                },
            )
            if forensics is not None and forensics.enabled:
                forensics.finalize(
                    export_completed=False,
                    aborted="strict missing aborted export" in str(exc).casefold(),
                    trace_path=trace.path,
                    log_path=get_cli_log_path(),
                    error=str(exc),
                )
            trace.close()
        raise
    finally:
        gateway.close()


def _resolve_target(
    gateway: NapCatGateway,
    chat_type: str,
    query: str,
    *,
    chat_name: str | None,
    refresh: bool,
) -> ChatTarget:
    if query.isdigit():
        try:
            return gateway.resolve_target(chat_type, query, refresh_if_missing=True)
        except NapCatTargetLookupError:
            return ChatTarget(chat_type=chat_type, chat_id=query, name=chat_name or query)
    return gateway.resolve_target(chat_type, query, refresh_if_missing=True)


def _build_cli_export_progress_callback(trace: ExportPerfTraceWriter):
    state: dict[str, object] = {
        "last_text": "",
        "last_emit": 0.0,
        "last_pages": -1,
        "last_current": -1,
    }

    def callback(update: dict[str, object]) -> None:
        phase = str(update.get("phase") or "progress")
        trace.write_event(phase, update)
        text = _format_cli_export_progress(update)
        if not text:
            return
        now = monotonic()
        if phase == "materialize_assets":
            current = int(update.get("current") or 0)
            total = int(update.get("total") or 0)
            last_current = int(state.get("last_current") or -1)
            if (
                current < total
                and current > last_current
                and current - last_current < 8
                and now - float(state.get("last_emit") or 0.0) < 0.25
            ):
                return
            state["last_current"] = current
        elif phase in {"bounds_scan", "interval_scan", "interval_tail_scan", "tail_scan", "full_scan"}:
            pages = int(update.get("pages_scanned") or 0)
            last_pages = int(state.get("last_pages") or -1)
            if pages == last_pages and now - float(state.get("last_emit") or 0.0) < 0.75:
                return
            state["last_pages"] = pages
        elif text == state.get("last_text"):
            return
        state["last_text"] = text
        state["last_emit"] = now
        typer.echo(text, err=True)

    return callback


def _format_cli_export_progress(update: dict[str, object]) -> str | None:
    phase = str(update.get("phase") or "")
    elapsed_s = float(update.get("elapsed_s") or 0.0)
    rate_suffix = (
        f" rate={float(update.get('rate_per_s') or 0.0):.1f}/s elapsed={elapsed_s:.1f}s"
        if elapsed_s > 0
        else ""
    )
    pages_scanned = int(update.get("pages_scanned") or 0)

    if phase in {"interval_scan", "interval_tail_scan", "tail_scan", "full_scan"}:
        page_size = int(update.get("page_size") or 0)
        page_duration_s = float(update.get("page_duration_s") or 0.0)
        history_source = str(update.get("history_source") or "")
        duration_label = "page"
        if history_source == "napcat_fast_history_bulk":
            duration_label = "bulk"
        if phase == "full_scan":
            collected_messages = int(update.get("collected_messages") or 0)
            detail = (
                f"export_progress: scanning full history pages={pages_scanned} "
                f"collected={collected_messages} page_size={page_size} {duration_label}={page_duration_s:.2f}s"
            )
        elif phase == "interval_scan":
            matched_messages = int(update.get("matched_messages") or 0)
            detail = (
                f"export_progress: scanning interval pages={pages_scanned} "
                f"matched={matched_messages} page_size={page_size} {duration_label}={page_duration_s:.2f}s"
            )
        else:
            matched_messages = int(update.get("matched_messages") or 0)
            requested_data_count = int(update.get("requested_data_count") or 0)
            label = "scanning recent tail" if phase == "tail_scan" else "scanning interval tail"
            detail = (
                f"export_progress: {label} pages={pages_scanned} "
                f"matched={matched_messages}/{requested_data_count} page_size={page_size} {duration_label}={page_duration_s:.2f}s"
            )
        if rate_suffix:
            detail += rate_suffix
        return detail

    if phase == "write_data_file":
        stage = str(update.get("stage") or "start")
        record_count = int(update.get("record_count") or 0)
        status = "wrote" if stage == "done" else "writing"
        return f"export_progress: {status} data file records={record_count}"

    if phase == "prefetch_media":
        stage = str(update.get("stage") or "start")
        request_count = int(update.get("request_count") or 0)
        if stage == "done":
            return f"export_progress: prefetched media context requests={request_count} elapsed={elapsed_s:.1f}s"
        if stage == "error":
            return f"export_progress: media prefetch degraded requests={request_count} elapsed={elapsed_s:.1f}s"
        return f"export_progress: prefetching media context requests={request_count}"

    if phase == "materialize_assets":
        current = int(update.get("current") or 0)
        total = int(update.get("total") or 0)
        asset_type = str(update.get("asset_type") or "-")
        asset_role = str(update.get("asset_role") or "").strip()
        role_suffix = f".{asset_role}" if asset_role else ""
        copied = int(update.get("copied_assets") or 0)
        reused = int(update.get("reused_assets") or 0)
        missing = int(update.get("missing_assets") or 0)
        errors = int(update.get("error_assets") or 0)
        detail = (
            f"export_progress: materializing assets {current}/{total} "
            f"{asset_type}{role_suffix} copied={copied} reused={reused} missing={missing} err={errors}"
        )
        if elapsed_s > 0 and current > 0:
            detail += f" rate={current / elapsed_s:.1f}/s elapsed={elapsed_s:.1f}s"
        return detail

    if phase == "forensic_incident" and str(update.get("stage") or "") == "recorded":
        if not bool(update.get("is_new_incident")):
            return None
        incident_id = str(update.get("incident_id") or "-")
        reason_category = str(update.get("reason_category") or "unknown")
        asset_type = str(update.get("asset_type") or "-")
        file_name = str(update.get("file_name") or "").strip() or "-"
        incident_path = str(update.get("incident_path") or "").strip()
        detail = (
            f"export_incident: {incident_id} reason={reason_category} "
            f"asset={asset_type}:{file_name}"
        )
        if incident_path:
            detail += f" forensic={incident_path}"
        return detail

    if phase == "materialize_asset_substep" and str(update.get("stage") or "") == "done":
        status = str(update.get("status") or "")
        if status not in {"timeout", "unavailable"}:
            return None
        substep = str(update.get("substep") or "-")
        asset_type = str(update.get("asset_type") or "-")
        file_name = str(update.get("file_name") or "").strip() or "-"
        timeout_s = float(update.get("timeout_s") or 0.0)
        elapsed = float(update.get("elapsed_s") or 0.0)
        detail = (
            f"export_progress: asset substep {status} substep={substep} "
            f"asset={asset_type}:{file_name}"
        )
        if timeout_s > 0:
            detail += f" timeout={timeout_s:.1f}s"
        if elapsed > 0:
            detail += f" elapsed={elapsed:.1f}s"
        return detail
    return None


def main() -> None:
    _init_cli_logging()
    app()


if __name__ == "__main__":
    main()
