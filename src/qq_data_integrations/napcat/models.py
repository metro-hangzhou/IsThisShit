from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from qq_data_core.models import EXPORT_TIMEZONE


class ChatTarget(BaseModel):
    chat_type: Literal["group", "private"]
    chat_id: str
    name: str
    remark: str | None = None
    aliases: list[str] = Field(default_factory=list)
    member_count: int | None = None
    extra: dict[str, Any] = Field(default_factory=dict)

    @property
    def display_name(self) -> str:
        return self.remark or self.name or self.chat_id

    @property
    def display_label(self) -> str:
        if self.display_name == self.chat_id:
            return self.chat_id
        return f"{self.display_name} ({self.chat_id})"

    def searchable_terms(self) -> list[str]:
        seen: set[str] = set()
        terms: list[str] = []
        for item in [self.chat_id, self.name, self.remark, *self.aliases]:
            value = (item or "").strip()
            lowered = value.casefold()
            if value and lowered not in seen:
                seen.add(lowered)
                terms.append(value)
        return terms


class MetadataCache(BaseModel):
    chat_type: Literal["group", "private"]
    refreshed_at: datetime | None = Field(default_factory=lambda: datetime.now(EXPORT_TIMEZONE))
    targets: list[ChatTarget] = Field(default_factory=list)


class ChatHistoryBounds(BaseModel):
    earliest_content_at: datetime | None = None
    final_content_at: datetime | None = None


class NapCatLoginStatus(BaseModel):
    is_login: bool = False
    is_offline: bool = False
    qrcode_url: str | None = None
    login_error: str | None = None

    def qr_expired(self) -> bool:
        message = (self.login_error or "").strip()
        return "二维码" in message and ("过期" in message or "失效" in message)

    def already_logged_in_elsewhere(self) -> bool:
        message = (self.login_error or "").strip()
        return "已登录" in message and ("无法重复登录" in message or "无需重复登录" in message)

    def effectively_logged_in(self) -> bool:
        return self.is_login or self.already_logged_in_elsewhere()


class NapCatLoginInfo(BaseModel):
    uin: str | None = None
    nick: str | None = None
    online: bool | None = None
    avatar_url: str | None = None
