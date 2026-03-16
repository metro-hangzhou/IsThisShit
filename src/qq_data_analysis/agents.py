from __future__ import annotations

from abc import ABC, abstractmethod
from collections import Counter
from typing import Any

from .models import AnalysisAgentOutput, AnalysisEvidenceItem, AnalysisMaterials


class BaseAnalysisAgent(ABC):
    agent_name = "base"
    agent_version = "v1"

    def prepare(self, materials: AnalysisMaterials) -> Any:
        return materials

    @abstractmethod
    def analyze(
        self, materials: AnalysisMaterials, prepared: Any
    ) -> AnalysisAgentOutput:
        raise NotImplementedError

    def serialize_result(self, output: AnalysisAgentOutput) -> dict[str, Any]:
        return output.compact_payload


class BaseStatsAgent(BaseAnalysisAgent):
    agent_name = "base_stats"
    agent_version = "v1"

    def analyze(
        self, materials: AnalysisMaterials, prepared: Any
    ) -> AnalysisAgentOutput:
        stats = materials.stats
        report = (
            "## Base Stats\n"
            f"- 分析对象: {materials.target.display_id}\n"
            f"- 时间窗口: {materials.chosen_time_window.start_timestamp_iso} "
            f"-> {materials.chosen_time_window.end_timestamp_iso}\n"
            f"- 消息数: {stats.message_count}\n"
            f"- 参与者数: {stats.sender_count}\n"
            f"- 图片占比: {stats.image_ratio:.2%}\n"
            f"- 转发占比: {stats.forward_ratio:.2%}\n"
            f"- 回复占比: {stats.reply_ratio:.2%}\n"
            f"- 表情占比: {stats.emoji_ratio:.2%}\n"
            f"- 低信息占比: {stats.low_information_ratio:.2%}"
        )
        return AnalysisAgentOutput(
            agent_name=self.agent_name,
            agent_version=self.agent_version,
            human_report=report,
            compact_payload={
                "msg_n": stats.message_count,
                "sender_n": stats.sender_count,
                "asset_n": stats.asset_count,
                "img_r": round(stats.image_ratio, 4),
                "fwd_r": round(stats.forward_ratio, 4),
                "reply_r": round(stats.reply_ratio, 4),
                "emoji_r": round(stats.emoji_ratio, 4),
                "low_r": round(stats.low_information_ratio, 4),
                "hrs": stats.hourly_distribution,
                "days": stats.daily_distribution,
            },
        )


class ContentCompositionAgent(BaseAnalysisAgent):
    agent_name = "content_composition"
    agent_version = "v1"

    def analyze(
        self, materials: AnalysisMaterials, prepared: Any
    ) -> AnalysisAgentOutput:
        top_tags = materials.tag_summaries[:5]
        top_events = materials.candidate_events[:3]
        top_people = materials.participant_profiles[:3]
        notes = self._build_notes(materials)
        evidence = self._collect_evidence(
            top_events, top_people, limit=max(3, len(top_events) * 2)
        )

        report_lines = ["## Content Composition"]
        if top_tags:
            report_lines.append(
                "- 主要成分标签: "
                + " / ".join(f"{item.tag}({item.count})" for item in top_tags)
            )
        else:
            report_lines.append("- 主要成分标签: 暂未命中明显异常标签")

        if notes:
            report_lines.append("- 观察摘要: " + "；".join(notes))

        if top_events:
            report_lines.append("- 重点事件:")
            for event in top_events:
                report_lines.append(
                    f"  - {event.start_timestamp_iso} -> {event.end_timestamp_iso} | "
                    f"{event.message_count} 条 | 标签: {', '.join(event.dominant_tags) or 'none'} | "
                    f"{event.summary}"
                )

        if top_people:
            report_lines.append("- 重点人物:")
            for person in top_people:
                tag_counter = Counter(person.tag_counts)
                tag_text = ", ".join(
                    f"{tag}:{count}" for tag, count in tag_counter.most_common(3)
                )
                report_lines.append(
                    f"  - {person.sender_id} | {person.message_count} 条 | "
                    f"标签: {tag_text or 'none'}"
                )

        return AnalysisAgentOutput(
            agent_name=self.agent_name,
            agent_version=self.agent_version,
            human_report="\n".join(report_lines),
            compact_payload={
                "tags": [
                    {
                        "t": item.tag,
                        "n": item.count,
                        "r": round(item.rate, 4),
                        "evi": item.evidence_message_uids[:3],
                    }
                    for item in top_tags
                ],
                "evts": [
                    {
                        "id": item.event_id,
                        "s": item.start_timestamp_iso,
                        "e": item.end_timestamp_iso,
                        "msg_n": item.message_count,
                        "sender_n": item.participant_count,
                        "tags": item.dominant_tags,
                        "sum": item.summary,
                        "evi": [e.message_uid for e in item.evidence[:3]],
                    }
                    for item in top_events
                ],
                "ppl": [
                    {
                        "sid": item.sender_id,
                        "sn": item.sender_name,
                        "msg_n": item.message_count,
                        "tags": item.tag_counts,
                        "evi": [e.message_uid for e in item.evidence[:3]],
                    }
                    for item in top_people
                ],
                "notes": notes,
                "themes": materials.theme_queries,
            },
            evidence=evidence,
        )

    def _build_notes(self, materials: AnalysisMaterials) -> list[str]:
        notes: list[str] = []
        tag_map = {item.tag: item for item in materials.tag_summaries}
        if "forward_nested" in tag_map:
            notes.append("存在明显的套娃转发/嵌套转发行为")
        if "low_information" in tag_map:
            notes.append("低信息量消息占比偏高")
        if "repetitive_noise" in tag_map:
            notes.append("存在重复噪声或重复刷屏现象")
        if "share_marker" in tag_map:
            notes.append("窗口内包含分享/卡片类上下文线索")
        if "system_marker" in tag_map:
            notes.append("窗口内包含系统提示或灰字提示上下文")
        if "media_gap" in tag_map:
            notes.append("窗口内存在缺失媒体证据，需要保留不确定性")
        if "absurd_or_bizarre" in tag_map:
            notes.append("存在怪诞或摸不着头脑的内容结构")
        if not notes and materials.theme_queries:
            notes.append("当前窗口更偏向普通内容成分分布，异常标签并不密集")
        return notes

    def _collect_evidence(
        self,
        events: list[Any],
        people: list[Any],
        *,
        limit: int,
    ) -> list[AnalysisEvidenceItem]:
        evidence: list[AnalysisEvidenceItem] = []
        seen: set[str] = set()
        for event in events:
            for item in event.evidence:
                if item.message_uid in seen:
                    continue
                evidence.append(item)
                seen.add(item.message_uid)
                if len(evidence) >= limit:
                    return evidence
        for person in people:
            for item in person.evidence:
                if item.message_uid in seen:
                    continue
                evidence.append(item)
                seen.add(item.message_uid)
                if len(evidence) >= limit:
                    return evidence
        return evidence


def build_default_agent_registry() -> dict[str, BaseAnalysisAgent]:
    return {
        "base_stats": BaseStatsAgent(),
        "content_composition": ContentCompositionAgent(),
    }
