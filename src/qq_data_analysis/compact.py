from __future__ import annotations

import json
from typing import Any


def dump_compact_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def load_compact_json(payload: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    return json.loads(payload)


def expand_compact_analysis(payload: str | dict[str, Any]) -> dict[str, Any]:
    data = load_compact_json(payload)
    expanded = {
        "run_id": data.get("rid"),
        "target": {
            "target_type": data.get("t", {}).get("tt"),
            "target_id": data.get("t", {}).get("id"),
            "target_name": data.get("t", {}).get("nm"),
        },
        "chosen_time_window": {
            "mode": data.get("win", {}).get("m"),
            "start_timestamp_ms": data.get("win", {}).get("s"),
            "end_timestamp_ms": data.get("win", {}).get("e"),
            "start_timestamp_iso": data.get("win", {}).get("si"),
            "end_timestamp_iso": data.get("win", {}).get("ei"),
            "rationale": data.get("win", {}).get("why"),
            "selected_message_count": data.get("win", {}).get("n"),
        },
        "agents": [],
    }

    for agent in data.get("ags", []):
        agent_data = agent.get("d", {})
        name = agent.get("n")
        if name == "base_stats":
            expanded["agents"].append(
                {
                    "agent_name": name,
                    "agent_version": agent.get("v"),
                    "data": {
                        "message_count": agent_data.get("msg_n"),
                        "sender_count": agent_data.get("sender_n"),
                        "asset_count": agent_data.get("asset_n"),
                        "image_ratio": agent_data.get("img_r"),
                        "forward_ratio": agent_data.get("fwd_r"),
                        "reply_ratio": agent_data.get("reply_r"),
                        "emoji_ratio": agent_data.get("emoji_r"),
                        "low_information_ratio": agent_data.get("low_r"),
                        "hourly_distribution": agent_data.get("hrs", {}),
                        "daily_distribution": agent_data.get("days", {}),
                    },
                }
            )
            continue
        if name == "content_composition":
            expanded["agents"].append(
                {
                    "agent_name": name,
                    "agent_version": agent.get("v"),
                    "data": {
                        "top_tags": agent_data.get("tags", []),
                        "events": agent_data.get("evts", []),
                        "people": agent_data.get("ppl", []),
                        "open_notes": agent_data.get("notes", []),
                        "theme_queries": agent_data.get("themes", []),
                    },
                }
            )
            continue
        expanded["agents"].append(
            {
                "agent_name": name,
                "agent_version": agent.get("v"),
                "data": agent_data,
            }
        )

    return expanded
