from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from qq_data_process.rag import RagService
from qq_data_process.rag_models import RetrievalConfig
from qq_data_process.utils import preview_text, stable_digest

from .models import (
    AnalysisEvidenceItem,
    AnalysisJobConfig,
    AnalysisMaterials,
    AnalysisMessageFeatures,
    AnalysisMessageRecord,
    AnalysisStatsSnapshot,
    AnalysisTagSummary,
    CandidateEvent,
    MediaCoverageSummary,
    ParticipantProfile,
    ResolvedAnalysisTarget,
    ResolvedTimeWindow,
)

EMOJI_TOKEN_RE = re.compile(r"\[(?:emoji:id=[^\]]+|sticker:[^\]]+)\]")
FORWARD_TOKEN_RE = re.compile(r"\[forward message\]")
UNSUPPORTED_TOKEN_RE = re.compile(r"\[unsupported:[^\]]+\]")


@dataclass(slots=True)
class _Session:
    messages: list[AnalysisMessageRecord]
    tags: Counter[str]
    score: float


class AnalysisSubstrate:
    def __init__(self, *, sqlite_path: Path, qdrant_path: Path) -> None:
        self.sqlite_path = sqlite_path
        self.qdrant_path = qdrant_path
        self._rag_service: RagService | None = None

    def close(self) -> None:
        if self._rag_service is not None:
            self._rag_service.close()
            self._rag_service = None

    def build_materials(self, config: AnalysisJobConfig) -> AnalysisMaterials:
        resolved_run_id = self._resolve_run_id(config.target.run_id)
        target = self._resolve_target(
            run_id=resolved_run_id,
            target_type=config.target.target_type,
            target_id=config.target.target_id,
            projection_mode=config.projection_mode,
            danger_allow_raw_identity_output=config.danger_allow_raw_identity_output,
        )
        all_messages = self._load_messages(
            run_id=resolved_run_id,
            target=target,
            projection_mode=config.projection_mode,
            danger_allow_raw_identity_output=config.danger_allow_raw_identity_output,
        )
        if not all_messages:
            raise RuntimeError(
                f"No messages were found for target {config.target.target_type}:{config.target.target_id}"
            )

        chosen_time_window = self._resolve_time_window(
            messages=all_messages, config=config
        )
        manifest_media_coverage = self._load_run_media_coverage(resolved_run_id)
        scoped_messages = [
            item
            for item in all_messages
            if chosen_time_window.start_timestamp_ms
            <= item.timestamp_ms
            <= chosen_time_window.end_timestamp_ms
        ]
        self._mark_repetitive_noise(scoped_messages)
        stats = self._build_stats(scoped_messages)
        tag_summaries = self._build_tag_summaries(scoped_messages)
        candidate_events = self._discover_candidate_events(
            scoped_messages,
            config=config,
            target=target,
            time_window=chosen_time_window,
        )
        participant_profiles = self._build_participant_profiles(
            scoped_messages,
            config=config,
        )
        theme_queries = self._derive_theme_queries(
            scoped_messages,
            config.max_theme_queries,
        )

        return AnalysisMaterials(
            run_id=resolved_run_id,
            target=target,
            chosen_time_window=chosen_time_window,
            messages=scoped_messages,
            stats=stats,
            manifest_media_coverage=manifest_media_coverage,
            tag_summaries=tag_summaries,
            candidate_events=candidate_events,
            participant_profiles=participant_profiles,
            theme_queries=theme_queries,
            warnings=[],
        )

    def _load_run_media_coverage(self, run_id: str) -> MediaCoverageSummary | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT payload_json FROM run_diagnostics
                WHERE run_id = ? AND diagnostic_kind = ?
                """,
                (run_id, "export_media_coverage"),
            ).fetchone()
        if row is None:
            return None
        return MediaCoverageSummary.model_validate(json.loads(row[0]))

    def _resolve_run_id(self, requested_run_id: str | None) -> str:
        with self._connect() as conn:
            if requested_run_id is not None:
                row = conn.execute(
                    "SELECT run_id FROM import_runs WHERE run_id = ?",
                    (requested_run_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT run_id FROM import_runs ORDER BY completed_at DESC LIMIT 1"
                ).fetchone()
        if row is None:
            raise RuntimeError("No preprocess runs were found in the SQLite state.")
        return str(row["run_id"])

    def _resolve_target(
        self,
        *,
        run_id: str,
        target_type: str,
        target_id: str,
        projection_mode: str,
        danger_allow_raw_identity_output: bool,
    ) -> ResolvedAnalysisTarget:
        if projection_mode == "raw" and not danger_allow_raw_identity_output:
            raise RuntimeError(
                "Raw-identity analysis requires danger_allow_raw_identity_output=True."
            )

        chat_type = "group" if target_type == "group" else "private"
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT c.chat_id_raw, c.chat_alias_id, c.chat_name_raw, c.chat_alias_label, c.chat_type
                FROM chats AS c
                JOIN messages AS m ON m.chat_id_raw = c.chat_id_raw
                WHERE c.chat_type = ?
                  AND m.run_id = ?
                  AND (c.chat_id_raw = ? OR c.chat_alias_id = ?)
                LIMIT 1
                """,
                (chat_type, run_id, target_id, target_id),
            ).fetchone()
        if row is None:
            raise RuntimeError(
                f"Target {target_type}:{target_id} was not found in run {run_id}."
            )

        display_id = row["chat_alias_id"]
        display_name = row["chat_alias_label"]
        if projection_mode == "raw":
            display_id = row["chat_id_raw"]
            display_name = row["chat_name_raw"]

        return ResolvedAnalysisTarget(
            target_type=target_type,
            raw_id=row["chat_id_raw"],
            alias_id=row["chat_alias_id"],
            display_id=display_id,
            display_name=display_name,
            run_id=run_id,
        )

    def _load_messages(
        self,
        *,
        run_id: str,
        target: ResolvedAnalysisTarget,
        projection_mode: str,
        danger_allow_raw_identity_output: bool,
    ) -> list[AnalysisMessageRecord]:
        if projection_mode == "raw" and not danger_allow_raw_identity_output:
            raise RuntimeError(
                "Raw-identity analysis requires danger_allow_raw_identity_output=True."
            )

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM messages
                WHERE run_id = ?
                  AND chat_id_raw = ?
                ORDER BY timestamp_ms ASC, message_uid ASC
                """,
                (run_id, target.raw_id),
            ).fetchall()
            if not rows:
                return []
            message_uids = [row["message_uid"] for row in rows]
            assets = self._load_assets(conn, message_uids)

        messages: list[AnalysisMessageRecord] = []
        for row in rows:
            sender_id = row["sender_alias_id"]
            sender_name = row["sender_alias_label"]
            chat_id = row["chat_alias_id"]
            chat_name = row["chat_alias_label"]
            if projection_mode == "raw":
                sender_id = row["sender_id_raw"]
                sender_name = row["sender_name_raw"]
                chat_id = row["chat_id_raw"]
                chat_name = row["chat_name_raw"]

            extra = json.loads(row["extra_json"])
            message_assets = assets.get(row["message_uid"], [])
            features = self._extract_message_features(
                content=row["content"],
                text_content=row["text_content"],
                extra=extra,
                assets=message_assets,
            )
            messages.append(
                AnalysisMessageRecord(
                    message_uid=row["message_uid"],
                    run_id=row["run_id"],
                    chat_type=row["chat_type"],
                    chat_id=chat_id,
                    chat_name=chat_name,
                    sender_id=sender_id,
                    sender_name=sender_name,
                    timestamp_ms=row["timestamp_ms"],
                    timestamp_iso=row["timestamp_iso"],
                    message_id=row["message_id"],
                    message_seq=row["message_seq"],
                    content=row["content"],
                    text_content=row["text_content"],
                    assets=message_assets,
                    extra=extra,
                    features=features,
                )
            )
        return messages

    def _resolve_time_window(
        self,
        *,
        messages: list[AnalysisMessageRecord],
        config: AnalysisJobConfig,
    ) -> ResolvedTimeWindow:
        if config.time_scope.mode == "manual":
            start = config.time_scope.start_timestamp_ms
            end = config.time_scope.end_timestamp_ms
            assert start is not None
            assert end is not None
            selected_count = sum(start <= item.timestamp_ms <= end for item in messages)
            return ResolvedTimeWindow(
                mode="manual",
                start_timestamp_ms=start,
                end_timestamp_ms=end,
                start_timestamp_iso=_ms_to_iso(start),
                end_timestamp_iso=_ms_to_iso(end),
                rationale="explicit user-provided range",
                selected_message_count=selected_count,
            )

        if len(messages) <= config.time_scope.min_messages_for_auto:
            start = messages[0].timestamp_ms
            end = messages[-1].timestamp_ms
            return ResolvedTimeWindow(
                mode="auto_adaptive",
                start_timestamp_ms=start,
                end_timestamp_ms=end,
                start_timestamp_iso=messages[0].timestamp_iso,
                end_timestamp_iso=messages[-1].timestamp_iso,
                rationale=(
                    "auto-adaptive fell back to the full available window because the "
                    "target message count is below the auto-selection threshold"
                ),
                selected_message_count=len(messages),
            )

        sessions = self._sessionize(messages, config.time_scope.session_gap_ms)
        chosen_session = max(
            sessions,
            key=lambda item: (item.score, len(item.messages)),
        )
        chosen = chosen_session.messages
        best_score = chosen_session.score
        _, best_notes = self._window_signal_score(chosen)
        return ResolvedTimeWindow(
            mode="auto_adaptive",
            start_timestamp_ms=chosen[0].timestamp_ms,
            end_timestamp_ms=chosen[-1].timestamp_ms,
            start_timestamp_iso=chosen[0].timestamp_iso,
            end_timestamp_iso=chosen[-1].timestamp_iso,
            rationale=(
                "auto-adaptive selected the highest-signal bounded session window "
                f"using a {config.time_scope.session_gap_ms // (60 * 1000)}m session gap "
                f"(signal_score={best_score:.2f}; {', '.join(best_notes)})"
            ),
            selected_message_count=len(chosen),
        )

    def _build_stats(
        self, messages: list[AnalysisMessageRecord]
    ) -> AnalysisStatsSnapshot:
        total = len(messages)
        if total == 0:
            return AnalysisStatsSnapshot(
                message_count=0,
                sender_count=0,
                asset_count=0,
                image_message_count=0,
                forward_message_count=0,
                reply_message_count=0,
                emoji_message_count=0,
                low_information_count=0,
                image_ratio=0.0,
                forward_ratio=0.0,
                reply_ratio=0.0,
                emoji_ratio=0.0,
                low_information_ratio=0.0,
            )

        hourly: Counter[str] = Counter()
        daily: Counter[str] = Counter()
        sender_ids = {item.sender_id for item in messages}
        asset_count = 0
        image_messages = 0
        forward_messages = 0
        reply_messages = 0
        emoji_messages = 0
        low_info_messages = 0
        for message in messages:
            hourly[message.timestamp_iso[:13]] += 1
            daily[message.timestamp_iso[:10]] += 1
            asset_count += len(message.assets)
            if message.features.image_count > 0:
                image_messages += 1
            if message.features.has_forward:
                forward_messages += 1
            if message.features.has_reply:
                reply_messages += 1
            if message.features.emoji_count > 0:
                emoji_messages += 1
            if message.features.low_information:
                low_info_messages += 1

        return AnalysisStatsSnapshot(
            message_count=total,
            sender_count=len(sender_ids),
            asset_count=asset_count,
            image_message_count=image_messages,
            forward_message_count=forward_messages,
            reply_message_count=reply_messages,
            emoji_message_count=emoji_messages,
            low_information_count=low_info_messages,
            image_ratio=image_messages / total,
            forward_ratio=forward_messages / total,
            reply_ratio=reply_messages / total,
            emoji_ratio=emoji_messages / total,
            low_information_ratio=low_info_messages / total,
            hourly_distribution=dict(hourly.most_common(12)),
            daily_distribution=dict(daily.most_common(12)),
        )

    def _build_tag_summaries(
        self, messages: list[AnalysisMessageRecord]
    ) -> list[AnalysisTagSummary]:
        total = len(messages) or 1
        tag_to_messages: defaultdict[str, set[str]] = defaultdict(set)
        evidence: defaultdict[str, list[str]] = defaultdict(list)

        event_tags = self._derive_aggregate_tags(messages)
        for tag in event_tags:
            for item in messages:
                if tag in item.features.message_tags or (
                    tag == "forward_nested" and item.features.forward_depth >= 2
                ):
                    tag_to_messages[tag].add(item.message_uid)
                    if item.message_uid not in evidence[tag] and len(evidence[tag]) < 3:
                        evidence[tag].append(item.message_uid)

        for message in messages:
            for tag in message.features.message_tags:
                tag_to_messages[tag].add(message.message_uid)
                if message.message_uid not in evidence[tag] and len(evidence[tag]) < 3:
                    evidence[tag].append(message.message_uid)

        summaries = [
            AnalysisTagSummary(
                tag=tag,
                count=len(message_uids),
                rate=len(message_uids) / total,
                open_notes=[],
                evidence_message_uids=evidence.get(tag, [])[:3],
            )
            for tag, message_uids in tag_to_messages.items()
            if message_uids
        ]
        summaries.sort(key=lambda item: (item.count, item.tag), reverse=True)
        return summaries

    def _discover_candidate_events(
        self,
        messages: list[AnalysisMessageRecord],
        *,
        config: AnalysisJobConfig,
        target: ResolvedAnalysisTarget,
        time_window: ResolvedTimeWindow,
    ) -> list[CandidateEvent]:
        sessions = self._sessionize(messages, config.time_scope.session_gap_ms)
        candidate_events: list[CandidateEvent] = []
        ordered_sessions = sorted(sessions, key=lambda item: item.score, reverse=True)
        for index, session in enumerate(
            ordered_sessions[: config.max_candidate_events]
        ):
            event_id = f"evt_{stable_digest(target.raw_id, index, session.messages[0].message_uid, length=12)}"
            evidence = self._event_evidence(
                session=session,
                target=target,
                time_window=time_window,
                config=config,
            )
            candidate_events.append(
                CandidateEvent(
                    event_id=event_id,
                    start_timestamp_ms=session.messages[0].timestamp_ms,
                    end_timestamp_ms=session.messages[-1].timestamp_ms,
                    start_timestamp_iso=session.messages[0].timestamp_iso,
                    end_timestamp_iso=session.messages[-1].timestamp_iso,
                    message_count=len(session.messages),
                    participant_count=len(
                        {item.sender_id for item in session.messages}
                    ),
                    dominant_tags=list(session.tags.keys())[:4],
                    summary=self._session_summary(session.messages, session.tags),
                    evidence=evidence[: config.max_evidence_items],
                )
            )
        return candidate_events

    def _build_participant_profiles(
        self,
        messages: list[AnalysisMessageRecord],
        *,
        config: AnalysisJobConfig,
    ) -> list[ParticipantProfile]:
        buckets: defaultdict[str, list[AnalysisMessageRecord]] = defaultdict(list)
        for message in messages:
            buckets[message.sender_id].append(message)

        profiles: list[ParticipantProfile] = []
        for sender_id, sender_messages in buckets.items():
            tag_counter: Counter[str] = Counter()
            evidence: list[AnalysisEvidenceItem] = []
            for message in sender_messages:
                tag_counter.update(message.features.message_tags)
                if (
                    len(evidence) < config.max_evidence_items
                    and message.features.message_tags
                ):
                    primary_reason = message.features.message_tags[0]
                    evidence.append(
                        AnalysisEvidenceItem(
                            message_uid=message.message_uid,
                            timestamp_iso=message.timestamp_iso,
                            sender_id=message.sender_id,
                            sender_name=message.sender_name,
                            content=preview_text(message.content, 80),
                            reason=f"sender-tagged:{primary_reason}",
                            tags=message.features.message_tags[:3],
                        )
                    )
            open_notes = self._profile_notes(sender_messages, tag_counter)
            profiles.append(
                ParticipantProfile(
                    sender_id=sender_id,
                    sender_name=sender_messages[0].sender_name,
                    message_count=len(sender_messages),
                    tag_counts=dict(tag_counter),
                    open_notes=open_notes,
                    evidence=evidence[: config.max_evidence_items],
                )
            )

        profiles.sort(
            key=lambda item: (item.message_count, sum(item.tag_counts.values())),
            reverse=True,
        )
        return profiles[: config.max_people]

    def _derive_theme_queries(
        self, messages: list[AnalysisMessageRecord], max_queries: int
    ) -> list[str]:
        candidates: list[str] = []
        seen: set[str] = set()
        for message in sorted(
            messages,
            key=lambda item: len(item.text_content or item.content),
            reverse=True,
        ):
            query = (message.text_content or message.content).strip()
            if len(query) < 4:
                continue
            if query in seen:
                continue
            if query.startswith("["):
                continue
            candidates.append(query[:24])
            seen.add(query)
            if len(candidates) >= max_queries:
                break
        return candidates

    def _event_evidence(
        self,
        *,
        session: _Session,
        target: ResolvedAnalysisTarget,
        time_window: ResolvedTimeWindow,
        config: AnalysisJobConfig,
    ) -> list[AnalysisEvidenceItem]:
        evidence: list[AnalysisEvidenceItem] = []
        seen: set[str] = set()

        tagged_messages = [
            item
            for item in session.messages
            if item.features.message_tags or item.features.forward_depth >= 2
        ]
        for message in tagged_messages[: config.max_evidence_items]:
            primary_reason = (
                message.features.message_tags[0]
                if message.features.message_tags
                else "tagged-message"
            )
            evidence.append(
                AnalysisEvidenceItem(
                    message_uid=message.message_uid,
                    timestamp_iso=message.timestamp_iso,
                    sender_id=message.sender_id,
                    sender_name=message.sender_name,
                    content=preview_text(message.content, 80),
                    reason=f"event-local:{primary_reason}",
                    tags=message.features.message_tags[:4],
                )
            )
            seen.add(message.message_uid)

        query_text = self._derive_session_query(session.messages)
        if query_text:
            for item in self._retrieve_supporting_evidence(
                query_text=query_text,
                target=target,
                time_window=time_window,
                config=config,
            ):
                if item.message_uid in seen:
                    continue
                evidence.append(item)
                seen.add(item.message_uid)
                if len(evidence) >= config.max_evidence_items:
                    break

        return evidence

    def _retrieve_supporting_evidence(
        self,
        *,
        query_text: str,
        target: ResolvedAnalysisTarget,
        time_window: ResolvedTimeWindow,
        config: AnalysisJobConfig,
    ) -> list[AnalysisEvidenceItem]:
        if not query_text.strip():
            return []
        retrieval = self._rag().retrieve(
            RetrievalConfig(
                query_text=query_text,
                run_id=target.run_id,
                chat_id_raw=target.raw_id,
                start_timestamp_ms=time_window.start_timestamp_ms,
                end_timestamp_ms=time_window.end_timestamp_ms,
                keyword_top_k=2,
                vector_top_k=2,
                top_k=2,
                projection_mode=config.projection_mode,
                danger_allow_raw_identity_output=config.danger_allow_raw_identity_output,
                max_context_blocks=2,
                max_messages_per_block=8,
            )
        )
        items: list[AnalysisEvidenceItem] = []
        for hit in retrieval.hits:
            items.append(
                AnalysisEvidenceItem(
                    message_uid=hit.message_uid,
                    timestamp_iso=hit.timestamp_iso,
                    sender_id=hit.sender_id,
                    sender_name=hit.sender_name,
                    content=preview_text(hit.content, 80),
                    reason=f"rag-support:{query_text}",
                    tags=hit.match_sources,
                )
            )
        return items

    def _sessionize(
        self, messages: list[AnalysisMessageRecord], session_gap_ms: int
    ) -> list[_Session]:
        sessions: list[list[AnalysisMessageRecord]] = []
        current: list[AnalysisMessageRecord] = []
        for message in messages:
            if not current:
                current = [message]
                continue
            if message.timestamp_ms - current[-1].timestamp_ms > session_gap_ms:
                sessions.append(current)
                current = [message]
                continue
            current.append(message)
        if current:
            sessions.append(current)

        output: list[_Session] = []
        for group in sessions:
            tags = Counter(self._derive_aggregate_tags(group))
            score, _ = self._window_signal_score(group)
            output.append(_Session(messages=group, tags=tags, score=score))
        return output

    def _window_signal_score(
        self, messages: list[AnalysisMessageRecord]
    ) -> tuple[float, list[str]]:
        total = len(messages)
        if total == 0:
            return 0.0, ["empty_window"]

        sender_count = len({item.sender_id for item in messages})
        reply_messages = sum(1 for item in messages if item.features.has_reply)
        forward_messages = sum(1 for item in messages if item.features.has_forward)
        nested_forwards = sum(
            1 for item in messages if item.features.forward_depth >= 2
        )
        low_info_messages = sum(1 for item in messages if item.features.low_information)
        repeated_noise = sum(1 for item in messages if item.features.repeated_noise)
        tags = self._derive_aggregate_tags(messages)
        share_or_system = sum(
            1
            for item in messages
            if _contains_keyword_marker(
                item.extra.get("source_payload", item.extra),
                ("share", "ark", "system", "graytip", "tip"),
            )
        )
        context_rich = (
            reply_messages + forward_messages + nested_forwards + share_or_system
        )
        low_info_ratio = low_info_messages / total
        image_only_burst = sum(
            1
            for item in messages
            if item.features.image_count > 0
            and item.features.low_information
            and not item.features.has_reply
            and not item.features.has_forward
        )

        score = total * 0.2
        score += sender_count * 1.25
        score += reply_messages * 2.5
        score += forward_messages * 2.75
        score += nested_forwards * 3.5
        score += share_or_system * 1.5
        score += len(tags) * 1.25
        score += context_rich * 2.5
        score -= low_info_messages * 1.75
        score -= repeated_noise * 1.5
        score -= image_only_burst * 2.0
        if low_info_ratio >= 0.5:
            score -= 4.0
        if context_rich <= 1:
            score -= 6.0

        notes = [
            f"messages={total}",
            f"senders={sender_count}",
            f"rich_context={context_rich}",
            f"tags={len(tags)}",
        ]
        if low_info_messages:
            notes.append(f"low_info_penalty={low_info_messages}")
        if repeated_noise:
            notes.append(f"repetitive_penalty={repeated_noise}")
        if image_only_burst and context_rich == 0:
            notes.append(f"media_only_penalty={image_only_burst}")
        if tags:
            notes.append(f"signals={'/'.join(tags[:3])}")

        return score, notes

    def _derive_aggregate_tags(
        self, messages: list[AnalysisMessageRecord]
    ) -> list[str]:
        tags: list[str] = []
        total = len(messages) or 1
        forward_messages = sum(1 for item in messages if item.features.has_forward)
        reply_messages = sum(1 for item in messages if item.features.has_reply)
        image_messages = sum(1 for item in messages if item.features.image_count > 0)
        emoji_messages = sum(1 for item in messages if item.features.emoji_count > 0)
        low_info_messages = sum(1 for item in messages if item.features.low_information)
        share_markers = sum(
            1 for item in messages if item.features.share_marker_count > 0
        )
        system_markers = sum(
            1 for item in messages if item.features.system_marker_count > 0
        )
        media_gaps = sum(
            1 for item in messages if item.features.missing_media_count > 0
        )
        nested_forwards = sum(
            1 for item in messages if item.features.forward_depth >= 2
        )
        repeated_noise = sum(1 for item in messages if item.features.repeated_noise)
        unsupported = sum(item.features.unsupported_count for item in messages)

        if nested_forwards > 0:
            tags.append("forward_nested")
        if forward_messages >= 3 and forward_messages / total >= 0.4:
            tags.append("forward_burst")
        if image_messages / total >= 0.35:
            tags.append("image_heavy")
        if emoji_messages / total >= 0.35:
            tags.append("emoji_heavy")
        if low_info_messages / total >= 0.3:
            tags.append("low_information")
        if reply_messages >= 3:
            tags.append("reply_chain")
        if repeated_noise >= 2:
            tags.append("repetitive_noise")
        if share_markers > 0:
            tags.append("share_marker")
        if system_markers > 0:
            tags.append("system_marker")
        if media_gaps > 0:
            tags.append("media_gap")
        if (
            self._topic_jump_score(messages) >= 0.6
            and len({item.sender_id for item in messages}) >= 3
        ):
            tags.append("topic_jump")
        if nested_forwards > 0 and (emoji_messages > 0 or repeated_noise > 0):
            tags.append("absurd_or_bizarre")
        if unsupported > 0 or (nested_forwards > 0 and reply_messages > 0):
            tags.append("confusing_context")
        return tags

    def _mark_repetitive_noise(self, messages: list[AnalysisMessageRecord]) -> None:
        normalized = Counter(
            self._normalize_repetition_key(item.content) for item in messages
        )
        for message in messages:
            key = self._normalize_repetition_key(message.content)
            if key and normalized[key] >= 3:
                message.features.repeated_noise = True
                if "repetitive_noise" not in message.features.message_tags:
                    message.features.message_tags.append("repetitive_noise")

    def _extract_message_features(
        self,
        *,
        content: str,
        text_content: str,
        extra: dict[str, Any],
        assets: list[dict[str, Any]],
    ) -> AnalysisMessageFeatures:
        image_count = sum(1 for item in assets if item["asset_type"] == "image")
        file_count = sum(1 for item in assets if item["asset_type"] == "file")
        emoji_count = len(EMOJI_TOKEN_RE.findall(content))
        unsupported_count = len(UNSUPPORTED_TOKEN_RE.findall(content))
        share_marker_count = int(
            _contains_keyword_marker(
                extra.get("source_payload", extra),
                ("share", "ark", "news"),
            )
        )
        system_marker_count = int(
            _contains_keyword_marker(
                extra.get("source_payload", extra),
                ("system", "graytip", "tip"),
            )
        )
        missing_media_count = sum(
            1 for item in assets if item.get("materialized", True) is False
        )
        forward_depth = max(
            len(FORWARD_TOKEN_RE.findall(content)),
            self._forward_depth(extra),
        )
        has_forward = forward_depth > 0
        has_reply = self._contains_reply(extra)
        low_information = self._is_low_information(
            content=content,
            text_content=text_content,
            image_count=image_count,
            emoji_count=emoji_count,
            has_forward=has_forward,
        )

        tags: list[str] = []
        if forward_depth >= 2:
            tags.append("forward_nested")
        if emoji_count > 0 and low_information:
            tags.append("emoji_heavy")
        if image_count > 0 and low_information:
            tags.append("image_heavy")
        if has_reply:
            tags.append("reply_chain")
        if share_marker_count > 0:
            tags.append("share_marker")
        if system_marker_count > 0:
            tags.append("system_marker")
        if missing_media_count > 0:
            tags.append("media_gap")
        if low_information:
            tags.append("low_information")
        if unsupported_count > 0:
            tags.append("confusing_context")

        return AnalysisMessageFeatures(
            image_count=image_count,
            file_count=file_count,
            emoji_count=emoji_count,
            share_marker_count=share_marker_count,
            system_marker_count=system_marker_count,
            missing_media_count=missing_media_count,
            has_reply=has_reply,
            has_forward=has_forward,
            forward_depth=forward_depth,
            low_information=low_information,
            unsupported_count=unsupported_count,
            message_tags=tags,
        )

    def _load_assets(
        self, conn: sqlite3.Connection, message_uids: Iterable[str]
    ) -> dict[str, list[dict[str, Any]]]:
        ordered = list(message_uids)
        if not ordered:
            return {}
        output: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        for chunk in _batched(ordered, 200):
            placeholders = ", ".join("?" for _ in chunk)
            rows = conn.execute(
                f"""
                SELECT asset_id, message_uid, asset_type, file_name, path, md5, extra_json
                FROM message_assets
                WHERE message_uid IN ({placeholders})
                """,
                chunk,
            ).fetchall()
            for row in rows:
                extra = json.loads(row["extra_json"])
                output[row["message_uid"]].append(
                    {
                        "asset_id": row["asset_id"],
                        "message_uid": row["message_uid"],
                        "asset_type": row["asset_type"],
                        "file_name": row["file_name"],
                        "path": row["path"],
                        "md5": row["md5"],
                        "extra": extra,
                        "materialized": extra.get("materialized", True),
                        "status": extra.get("materialization_status"),
                        "resolver": extra.get("materialization_resolver"),
                        "exported_rel_path": extra.get(
                            "materialization_exported_rel_path"
                        ),
                    }
                )
        return dict(output)

    def _contains_reply(self, extra: dict[str, Any]) -> bool:
        source_payload = extra.get("source_payload", {})
        if isinstance(source_payload, dict) and source_payload.get("reply_to"):
            return True
        return _contains_marker(source_payload, marker="reply")

    def _forward_depth(self, extra: dict[str, Any]) -> int:
        source_payload = extra.get("source_payload", extra)
        return _forward_depth(source_payload)

    def _is_low_information(
        self,
        *,
        content: str,
        text_content: str,
        image_count: int,
        emoji_count: int,
        has_forward: bool,
    ) -> bool:
        stripped = (text_content or "").strip()
        if not stripped:
            return image_count > 0 or emoji_count > 0 or has_forward
        if len(stripped) <= 2:
            return True
        if len(stripped) <= 4 and (emoji_count > 0 or image_count > 0):
            return True
        if content in {"?", "？", "草", "艹", "6"}:
            return True
        return False

    def _topic_jump_score(self, messages: list[AnalysisMessageRecord]) -> float:
        comparable: list[tuple[set[str], int]] = []
        for item in messages:
            text = (item.text_content or item.content).strip()
            if len(text) < 2:
                continue
            comparable.append((_character_tokens(text), item.timestamp_ms))
        if len(comparable) < 3:
            return 0.0
        zero_overlap = 0
        comparisons = 0
        for previous, current in zip(comparable, comparable[1:]):
            if current[1] - previous[1] > 5 * 60 * 1000:
                continue
            comparisons += 1
            if _jaccard(previous[0], current[0]) < 0.1:
                zero_overlap += 1
        if comparisons == 0:
            return 0.0
        return zero_overlap / comparisons

    def _profile_notes(
        self, messages: list[AnalysisMessageRecord], tags: Counter[str]
    ) -> list[str]:
        notes: list[str] = []
        total = len(messages) or 1
        image_ratio = (
            sum(1 for item in messages if item.features.image_count > 0) / total
        )
        if tags.get("forward_nested", 0) > 0:
            notes.append("存在明显套娃转发参与")
        if image_ratio >= 0.35:
            notes.append("图片占比偏高")
        if tags.get("repetitive_noise", 0) >= 2:
            notes.append("重复噪声偏多")
        if tags.get("low_information", 0) >= max(2, total // 3):
            notes.append("低信息互动偏多")
        return notes

    def _derive_session_query(self, messages: list[AnalysisMessageRecord]) -> str:
        for message in sorted(
            messages,
            key=lambda item: len(item.text_content or item.content),
            reverse=True,
        ):
            candidate = (message.text_content or message.content).strip()
            if len(candidate) >= 4 and not candidate.startswith("["):
                return candidate[:24]
        return ""

    def _session_summary(
        self, messages: list[AnalysisMessageRecord], tags: Counter[str]
    ) -> str:
        preview = ""
        for message in messages:
            candidate = (message.text_content or message.content).strip()
            if candidate:
                preview = preview_text(candidate, 36)
                break
        if not preview:
            preview = preview_text(messages[0].content, 36)
        if tags:
            return f"{preview} | tags={','.join(tags.keys())}"
        return preview

    def _normalize_repetition_key(self, content: str) -> str:
        key = re.sub(r"\s+", "", content.strip())
        if len(key) > 32:
            return key[:32]
        return key

    def _rag(self) -> RagService:
        if self._rag_service is None:
            self._rag_service = RagService.from_state(
                sqlite_path=self.sqlite_path,
                qdrant_path=self.qdrant_path,
            )
        return self._rag_service

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        return conn


def _ms_to_iso(value: int) -> str:
    return (
        datetime.fromtimestamp(value / 1000, tz=timezone.utc).astimezone().isoformat()
    )


def _batched(items: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def _character_tokens(text: str) -> set[str]:
    return {
        item
        for item in text
        if not item.isspace() and item not in "[](){}<>:：,，。.!！？?\"'`"
    }


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _contains_marker(value: Any, *, marker: str) -> bool:
    if isinstance(value, dict):
        value_type = str(value.get("type", "")).lower()
        if marker in value_type:
            return True
        return any(_contains_marker(item, marker=marker) for item in value.values())
    if isinstance(value, list):
        return any(_contains_marker(item, marker=marker) for item in value)
    return False


def _contains_keyword_marker(value: Any, keywords: tuple[str, ...]) -> bool:
    lowered = tuple(item.lower() for item in keywords)
    if isinstance(value, dict):
        for key, item in value.items():
            if any(word in str(key).lower() for word in lowered):
                return True
            if _contains_keyword_marker(item, keywords):
                return True
        value_type = str(value.get("type", "")).lower()
        return any(word in value_type for word in lowered)
    if isinstance(value, list):
        return any(_contains_keyword_marker(item, keywords) for item in value)
    if isinstance(value, str):
        text = value.lower()
        return any(word in text for word in lowered)
    return False


def _forward_depth(value: Any, depth: int = 0) -> int:
    best = depth
    if isinstance(value, dict):
        value_type = str(value.get("type", "")).lower()
        has_forward_shape = "forward" in value_type or any(
            "forward" in str(key).lower() for key in value.keys()
        )
        next_depth = depth + 1 if has_forward_shape else depth
        best = max(best, next_depth)
        for item in value.values():
            best = max(best, _forward_depth(item, next_depth))
    elif isinstance(value, list):
        for item in value:
            best = max(best, _forward_depth(item, depth))
    return best
