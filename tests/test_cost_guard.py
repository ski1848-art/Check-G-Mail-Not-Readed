"""
AI 비용 절감 + 재발 방지 회귀 테스트

이 테스트들은 다음 두 가지를 코드로 못박아 재발을 방지한다:
  1. 비용 절감: 중요도 '판단'에는 본문을 넣지 않고, 알림 대상(NOTIFY) 메일만
     본문으로 요약한다 → 무시할 메일의 본문을 읽어 비용이 새는 일 방지.
  2. 급증 감지: 최근 평균 대비(특히 통당 비용) 급증을 잡아낸다 → 고정 한도
     아래에서 조용히 몇 배로 뛰는 상황(과거 7배 사례)을 다음 날 즉시 포착.
"""
import sys
import os
from datetime import datetime
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import Config
from app.models import GmailEvent, AnalysisResult, ImportanceCategory, AnalysisSource
from app.services.llm_service import LLMService
from app.core.classifier import Classifier


def _make_event(body: str = "이것은 메일 본문입니다. 상세 정보가 여기에 들어갑니다.") -> GmailEvent:
    return GmailEvent(
        timestamp=datetime.now(),
        message_id="test_cost_guard_001",
        subject="테스트 제목",
        sender="sender@example.com",
        recipients=["recipient@example.com"],
        owner="owner@example.com",
        event_type="RECEIVE",
        raw_data={"snippet": "미리보기 스니펫", "body_text": body, "gmail_id": "g1"},
    )


_FIXED_CONFIG = {
    "blacklist_domains": [], "whitelist_domains": [], "spam_keywords": [],
    "urgent_keywords": [], "noreply_patterns": [], "score_threshold_notify": 0.5,
}


# ---------------------------------------------------------------------------
# 1. 본문은 '판단'이 아니라 '요약'에만 쓰인다
# ---------------------------------------------------------------------------

class TestBodyOnlyForSummary:
    def test_build_user_prompt_include_body_flag(self):
        """include_body=False면 본문이 프롬프트에서 빠져야 한다."""
        svc = LLMService()
        ev = _make_event(body="여기에상세본문내용포함")
        with_body = svc._build_user_prompt(ev, include_body=True)
        without_body = svc._build_user_prompt(ev, include_body=False)
        assert "여기에상세본문내용포함" in with_body
        assert "Body:" in with_body
        assert "여기에상세본문내용포함" not in without_body
        assert "Body:" not in without_body

    def test_analyze_email_excludes_body_from_judgment(self, monkeypatch):
        """중요도 판단(analyze_email)은 본문 없이 호출되어야 한다 (비용 절감 핵심)."""
        svc = LLMService()
        svc.client = None
        svc.tw_client = None  # 실제 API 호출 방지 (폴백 경로)
        captured = {}
        orig = svc._build_user_prompt

        def spy(event, upm=None, include_body=True):
            captured["include_body"] = include_body
            return orig(event, upm, include_body)

        monkeypatch.setattr(svc, "_build_user_prompt", spy)
        svc.analyze_email(_make_event())
        assert captured.get("include_body") is False

    def test_summary_body_cap_is_bounded(self):
        """회귀 방지: 요약 본문 상한이 과도하게 커지지 않도록 고정."""
        assert 0 < Config.LLM_SUMMARY_BODY_MAX_CHARS <= 2000


# ---------------------------------------------------------------------------
# 2. 무시할(SILENT) 메일은 본문 요약을 호출하지 않는다
# ---------------------------------------------------------------------------

class TestClassifierBodyGating:
    def _make_classifier(self, monkeypatch, category, score):
        clf = Classifier()
        monkeypatch.setattr(clf, "_get_filter_config", lambda: dict(_FIXED_CONFIG))
        monkeypatch.setattr(
            clf.llm_service, "analyze_email",
            lambda event, upm=None: AnalysisResult(
                score=score, category=category, reason="mock", source=AnalysisSource.LLM,
            ),
        )
        calls = []

        def fake_summarize(event):
            calls.append(event)
            return ("• 요약 첫째 줄\n• 요약 둘째 줄", {"input_tokens": 80, "output_tokens": 30})

        monkeypatch.setattr(clf.llm_service, "summarize_email", fake_summarize)
        return clf, calls

    def test_silent_email_does_not_read_body(self, monkeypatch):
        clf, calls = self._make_classifier(monkeypatch, ImportanceCategory.SILENT, 0.1)
        result = clf.classify(_make_event())
        assert result.category == ImportanceCategory.SILENT
        assert calls == [], "SILENT 메일은 본문 요약(summarize_email)을 호출하면 안 된다"

    def test_notify_email_reads_body_for_summary(self, monkeypatch):
        clf, calls = self._make_classifier(monkeypatch, ImportanceCategory.NOTIFY, 0.9)
        result = clf.classify(_make_event())
        assert result.category == ImportanceCategory.NOTIFY
        assert len(calls) == 1, "NOTIFY 메일은 본문 요약을 1회 호출해야 한다"
        assert result.summary == "• 요약 첫째 줄\n• 요약 둘째 줄"
        assert result.llm_usage is not None


# ---------------------------------------------------------------------------
# 3. 사용량 결과에 토큰 사용량이 담긴다 (스레드 안전 집계)
# ---------------------------------------------------------------------------

class TestUsageAttachment:
    def test_merge_usage_sums_tokens(self):
        a = {"input_tokens": 100, "output_tokens": 20, "cache_write_tokens": 0, "cache_read_tokens": 0}
        b = {"input_tokens": 50, "output_tokens": 10, "cache_write_tokens": 5, "cache_read_tokens": 0}
        merged = LLMService._merge_usage(a, b)
        assert merged["input_tokens"] == 150
        assert merged["output_tokens"] == 30
        assert merged["cache_write_tokens"] == 5
        assert LLMService._merge_usage(None, b) == b
        assert LLMService._merge_usage(a, None) == a
        assert LLMService._merge_usage(None, None) is None

    def test_analyze_email_attaches_usage_to_result(self):
        """분석 결과 객체에 llm_usage가 담겨야 한다 (공유 상태 대신 결과로 전달)."""
        svc = LLMService()
        svc.tw_client = None
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = '{"score":0.9,"category":"notify","reason":"r","summary":"이것은 충분히 긴 요약입니다","user_overrides":{}}'
        resp = MagicMock()
        resp.content = [text_block]
        usage = MagicMock()
        usage.input_tokens = 500
        usage.output_tokens = 100
        usage.cache_creation_input_tokens = 0
        usage.cache_read_input_tokens = 0
        resp.usage = usage
        svc.client = MagicMock()
        svc.client.messages.create.return_value = resp

        result = svc.analyze_email(_make_event())
        assert result.llm_usage is not None
        assert result.llm_usage["input_tokens"] == 500
        assert result.llm_usage["output_tokens"] == 100


# ---------------------------------------------------------------------------
# 4. 급증 감지 로직 (최근 평균 대비 통당 비용/총비용 급증)
# ---------------------------------------------------------------------------

class TestUsageSpikeDetection:
    def _store(self, monkeypatch, recent, min_calls=20, mult=3.0):
        from app.services.settings_store import SettingsStore
        s = SettingsStore()
        monkeypatch.setattr(s, "db", object())  # truthy → early-return 방지 (테스트 후 복원)
        monkeypatch.setattr(s, "get_recent_daily_usages", lambda days=7: recent)
        monkeypatch.setattr(
            s, "get_setting",
            lambda k, d=None: {"usage_spike_min_calls": min_calls, "usage_spike_multiplier": mult}.get(k, d),
        )
        return s

    def test_detects_per_call_cost_jump(self, monkeypatch):
        """통당 비용이 최근 평균의 7배로 뛰면 급증으로 잡아야 한다 (과거 사례)."""
        recent = [{"date": f"d{i}", "calls": 100, "cost_usd": 0.05} for i in range(5)]
        today = {"date": "today", "calls": 100, "cost_usd": 0.35}  # 통당 7배
        s = self._store(monkeypatch, recent)
        is_spike, detail = s.check_usage_spike(today_usage=today)
        assert is_spike is True
        assert "급증" in detail["kind"]

    def test_flat_usage_no_alert(self, monkeypatch):
        """평소와 비슷하면 급증 아님."""
        recent = [{"date": f"d{i}", "calls": 100, "cost_usd": 0.05} for i in range(5)]
        today = {"date": "today", "calls": 110, "cost_usd": 0.055}
        s = self._store(monkeypatch, recent)
        is_spike, _ = s.check_usage_spike(today_usage=today)
        assert is_spike is False

    def test_insufficient_sample_no_alert(self, monkeypatch):
        """오늘 표본(건수)이 최소치 미만이면 오탐 방지를 위해 판정 보류."""
        recent = [{"date": f"d{i}", "calls": 100, "cost_usd": 0.05} for i in range(5)]
        today = {"date": "today", "calls": 5, "cost_usd": 0.35}
        s = self._store(monkeypatch, recent, min_calls=20)
        is_spike, _ = s.check_usage_spike(today_usage=today)
        assert is_spike is False

    def test_too_few_history_days_no_alert(self, monkeypatch):
        """과거 표본이 3일 미만이면 판정 보류."""
        recent = [{"date": "d1", "calls": 100, "cost_usd": 0.05}]
        today = {"date": "today", "calls": 100, "cost_usd": 0.35}
        s = self._store(monkeypatch, recent)
        is_spike, _ = s.check_usage_spike(today_usage=today)
        assert is_spike is False
