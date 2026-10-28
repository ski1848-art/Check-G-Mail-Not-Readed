"""Slack header 블록 150자 한도 + 버튼 value 2000자 한도 회귀 테스트.

운영 관찰(2026-10-28, Firestore email_events 30일 집계): 제목이 149자 이상인 메일(AWS 안내,
일본 거래처 회신 체인)은 제목을 150자로 자른 뒤 "📧 " 접두어를 붙여 152자가 되어 Slack이
invalid_blocks 로 거절 → 처리 완료 표시가 안 남아 5분마다 재시도·재실패, 알림 영구 누락.
30일간 알림 945건 중 9건이 이렇게 유실됐다(제목 169~200자).
"""
from datetime import datetime, timezone

import pytest

from app.models import AnalysisResult, AnalysisSource, GmailEvent, ImportanceCategory
from app.services.slack_service import (
    HEADER_ELLIPSIS,
    HEADER_PREFIX,
    HEADER_TOTAL_MAX_LEN,
    SLACK_HEADER_MAX_LEN,
    SlackService,
    build_header_text,
    utf16_len,
)

SLACK_BUTTON_VALUE_MAX_LEN = 2000  # Slack button value 한도

# 실제 유실된 제목과 같은 모양(일본어 회신 체인, 전각 공백 포함)의 합성 제목. 실명·사명 없음.
SYNTHETIC_JP_CHAIN = (
    "Re: 【案件A】11/10最終版→【担当者様】11/10掲載お願いいたします　"
    "→Re: 【案件A】順番変更→【担当者様】コメント順の変更依頼　"
    "→Re: 【案件A】お客様の声差し替え→【担当者様】お客様の声について　"
    "→Re: 【案件A】11/10修正版をお送りいたします→Re: 【案件A】11/10コンテンツ送付"
)

PREFIX_UNITS = utf16_len(HEADER_PREFIX)                  # 3 (이모지 2 + 공백 1)
SUBJECT_BUDGET = HEADER_TOTAL_MAX_LEN - PREFIX_UNITS      # 142
BODY_BUDGET = SUBJECT_BUDGET - utf16_len(HEADER_ELLIPSIS)  # 139


class TestUtf16Len:
    def test_bmp_chars_count_one(self):
        assert utf16_len("가あx") == 3

    def test_emoji_counts_two(self):
        assert utf16_len("📧") == 2
        assert utf16_len(HEADER_PREFIX) == 3


class TestBuildHeaderText:
    def test_short_subject_kept_with_prefix(self):
        assert build_header_text("정산 안내") == f"{HEADER_PREFIX}정산 안내"

    def test_none_subject(self):
        assert build_header_text(None) == f"{HEADER_PREFIX}(제목 없음)"

    def test_empty_subject(self):
        assert build_header_text("") == f"{HEADER_PREFIX}(제목 없음)"

    def test_subject_at_budget_is_not_truncated(self):
        subject = "x" * SUBJECT_BUDGET
        out = build_header_text(subject)
        assert out == f"{HEADER_PREFIX}{subject}"
        assert utf16_len(out) == HEADER_TOTAL_MAX_LEN

    def test_one_over_budget_is_truncated_to_exact_value(self):
        subject = "제" * (SUBJECT_BUDGET + 1)
        assert build_header_text(subject) == f"{HEADER_PREFIX}{'제' * BODY_BUDGET}{HEADER_ELLIPSIS}"

    @pytest.mark.parametrize("n", [148, 149, 150, 151, 152, 169, 175, 180, 200, 400])
    def test_bug_lengths_are_within_slack_limit(self, n):
        # 예전 버그 경계(149~152)와 운영에서 실제 유실된 길이(169/175/180/200)
        out = build_header_text("あ" * n)
        assert out == f"{HEADER_PREFIX}{'あ' * BODY_BUDGET}{HEADER_ELLIPSIS}"   # 정확값
        assert utf16_len(out) == HEADER_TOTAL_MAX_LEN <= SLACK_HEADER_MAX_LEN

    def test_every_length_up_to_1000_is_within_limit(self):
        for n in range(0, 1001):
            assert utf16_len(build_header_text("제" * n)) <= HEADER_TOTAL_MAX_LEN

    def test_emoji_subject_counts_utf16_units_and_never_splits_pair(self):
        subject = "😀" * 200                      # 400 유닛
        out = build_header_text(subject)
        assert utf16_len(out) <= HEADER_TOTAL_MAX_LEN
        assert out.endswith(HEADER_ELLIPSIS)
        body = out[len(HEADER_PREFIX):-len(HEADER_ELLIPSIS)]
        assert set(body) == {"😀"}               # 서로게이트 쌍이 깨지지 않음
        assert utf16_len(body) == BODY_BUDGET - 1  # 139는 홀수라 이모지 69개(138)까지만

    def test_mixed_emoji_in_subject(self):
        subject = "🙅‍♂️ 당첨자 추첨 " * 30
        assert utf16_len(build_header_text(subject)) <= HEADER_TOTAL_MAX_LEN

    def test_synthetic_japanese_reply_chain(self):
        assert len(SYNTHETIC_JP_CHAIN) >= 149  # 전제: 예전 코드라면 152자가 되어 거절됐을 길이
        out = build_header_text(SYNTHETIC_JP_CHAIN)
        assert utf16_len(out) <= SLACK_HEADER_MAX_LEN
        assert out.startswith(HEADER_PREFIX) and out.endswith(HEADER_ELLIPSIS)


def _service(monkeypatch):
    # 토큰 없이도 블록 조립만 검증 (WebClient 생성 안 함)
    from app.services import slack_service as mod
    monkeypatch.setattr(mod.Config, "SLACK_BOT_TOKEN", None, raising=False)
    return SlackService()


def _event(subject: str) -> GmailEvent:
    return GmailEvent(
        timestamp=datetime.now(timezone.utc),
        message_id="<test-long-subject@example.com>",
        subject=subject,
        sender="no-reply@example.com",
        recipients=["owner@example.com"],
        owner="owner@example.com",
        event_type="RECEIVE",
    )


def _analysis() -> AnalysisResult:
    return AnalysisResult(
        score=0.9, category=ImportanceCategory.NOTIFY, reason="테스트",
        summary="• 요약 1\n• 요약 2", source=AnalysisSource.LLM,
    )


def _button(blocks, action_id):
    for b in blocks:
        if b.get("type") == "actions":
            for el in b["elements"]:
                if el.get("action_id") == action_id:
                    return el
    raise AssertionError(f"{action_id} 버튼 없음")


class TestBuildBlocks:
    def test_header_block_within_limit_for_long_subject(self, monkeypatch):
        svc = _service(monkeypatch)
        subject = "[Notification] " + "Upcoming routine retirement of your container tasks " * 4
        assert len(subject) > SLACK_HEADER_MAX_LEN
        blocks = svc._build_blocks(_event(subject), _analysis())
        header = blocks[0]
        assert header["type"] == "header"
        assert utf16_len(header["text"]["text"]) <= SLACK_HEADER_MAX_LEN
        assert header["text"]["text"].startswith(HEADER_PREFIX)

    def test_block_button_value_not_inflated_by_ascii_escaping(self, monkeypatch):
        # 한글·일본어 제목이 \uXXXX 로 6배 부풀어 2000자 한도를 넘지 않아야 함
        svc = _service(monkeypatch)
        subject = SYNTHETIC_JP_CHAIN * 2            # 300자 이상의 일본어 제목
        assert len(subject) >= 300
        blocks = svc._build_blocks(_event(subject), _analysis())
        value = _button(blocks, "silent_forever")["value"]
        assert len(value) <= SLACK_BUTTON_VALUE_MAX_LEN
        assert "\\u" not in value                    # 이스케이프로 부풀지 않음
        assert subject in value                      # 제목 원문이 그대로 담김(차단 패턴 추출용)

    def test_mark_as_read_button_value_short(self, monkeypatch):
        svc = _service(monkeypatch)
        blocks = svc._build_blocks(_event("짧은 제목"), _analysis())
        value = _button(blocks, "mark_as_read_gmail")["value"]
        assert len(value) <= SLACK_BUTTON_VALUE_MAX_LEN
