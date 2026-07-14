"""
Preservation Property Tests — 기존 동작 유지 검증

수정 전 코드에서 PASS가 예상됩니다 (기존 동작 보존 확인).
수정 후 코드에서도 PASS가 예상됩니다 (회귀 없음 확인).

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**
"""
import json
import sys
import os
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import GmailEvent, AnalysisResult, ImportanceCategory, AnalysisSource
from app.services.llm_service import LLMService
from app.core.classifier import Classifier


# ---------------------------------------------------------------------------
# Strategies & Helpers
# ---------------------------------------------------------------------------

ENGLISH_SUBJECTS = [
    "Weekly team sync meeting",
    "Project update: Q4 deliverables",
    "Invoice #12345 attached",
    "Re: Partnership proposal discussion",
    "Meeting notes from Monday",
    "Action items from sprint review",
    "Budget approval request",
    "New hire onboarding schedule",
    "Client feedback summary",
    "Quarterly performance review",
]

ENGLISH_SNIPPETS = [
    "Hi team, please find the updated project timeline attached.",
    "Following up on our discussion from last week regarding the budget.",
    "The quarterly report has been finalized and is ready for review.",
    "Please confirm your availability for the meeting next Tuesday.",
    "I wanted to share the latest client feedback with the team.",
]

english_subject_strategy = st.sampled_from(ENGLISH_SUBJECTS)
english_snippet_strategy = st.sampled_from(ENGLISH_SNIPPETS)


def _make_gmail_event(
    subject: str = "Test email",
    snippet: str = "This is a test snippet for the email.",
    sender: str = "sender@example.com",
    recipients: list = None,
    owner: str = "owner@example.com",
    raw_data: dict = None,
) -> GmailEvent:
    """테스트용 GmailEvent 생성 헬퍼"""
    if recipients is None:
        recipients = ["recipient@example.com"]
    if raw_data is None:
        raw_data = {"snippet": snippet, "gmail_id": "test_msg_001"}
    return GmailEvent(
        timestamp=datetime.now(),
        message_id="test_msg_001",
        subject=subject,
        sender=sender,
        recipients=recipients,
        owner=owner,
        event_type="RECEIVE",
        raw_data=raw_data,
    )


# ---------------------------------------------------------------------------
# Test 1: _build_system_prompt() 영문 메일 구조 보존
# **Validates: Requirements 3.1**
#
# 현재 코드: 영어 프롬프트에 JSON 형식 지시 포함
# 보존: 수정 후에도 동일한 구조(JSON 형식, score/category/reason/summary 필드)를 유지
# ---------------------------------------------------------------------------

class TestSystemPromptStructurePreservation:
    """영문 메일에 대한 시스템 프롬프트 구조가 보존되어야 함"""

    @given(subject=english_subject_strategy)
    @settings(max_examples=20)
    def test_system_prompt_maintains_json_response_structure(self, subject):
        """
        Property: 랜덤 영문 메일 이벤트에 대해 _build_system_prompt() 반환값이
        기존과 동일한 구조(JSON 형식 지시, 필수 필드)를 유지하는지 검증.

        **Validates: Requirements 3.1**
        """
        service = LLMService()
        prompt = service._build_system_prompt()

        # 시스템 프롬프트는 문자열이어야 함
        assert isinstance(prompt, str), "시스템 프롬프트는 문자열이어야 합니다."
        assert len(prompt) > 0, "시스템 프롬프트가 비어있으면 안 됩니다."

        # JSON 응답 형식 지시가 포함되어야 함
        assert "JSON" in prompt or "json" in prompt, (
            "시스템 프롬프트에 JSON 응답 형식 지시가 포함되어야 합니다."
        )

        # 필수 필드(score, category, reason, summary)가 프롬프트에 언급되어야 함
        prompt_lower = prompt.lower()
        assert "score" in prompt_lower, "시스템 프롬프트에 'score' 필드가 언급되어야 합니다."
        assert "category" in prompt_lower, "시스템 프롬프트에 'category' 필드가 언급되어야 합니다."
        assert "reason" in prompt_lower, "시스템 프롬프트에 'reason' 필드가 언급되어야 합니다."
        assert "summary" in prompt_lower, "시스템 프롬프트에 'summary' 필드가 언급되어야 합니다."

        # notify/silent 분류 기준이 포함되어야 함
        assert "notify" in prompt_lower, "시스템 프롬프트에 'notify' 분류 기준이 포함되어야 합니다."
        assert "silent" in prompt_lower, "시스템 프롬프트에 'silent' 분류 기준이 포함되어야 합니다."


# ---------------------------------------------------------------------------
# Test 2: _parse() 유효한 summary(10자 이상) 정상 반환 보존
# **Validates: Requirements 3.1**
#
# 현재 코드: summary를 그대로 반환
# 보존: 유효한 summary(10자 이상)는 수정 후에도 정상 반환
# ---------------------------------------------------------------------------

# Strategy: 10자 이상의 유효한 영문/한국어 summary 생성
valid_summary_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=10,
    max_size=200,
).filter(lambda s: len(s.strip()) >= 10)


class TestParseValidSummaryPreservation:
    """_parse()가 유효한 summary(10자 이상)를 정상 반환해야 함"""

    @given(
        score=st.floats(min_value=0.0, max_value=1.0),
        category=st.sampled_from(["notify", "silent"]),
        summary=valid_summary_strategy,
    )
    @settings(max_examples=30)
    def test_parse_returns_valid_summary_unchanged(self, score, category, summary):
        """
        Property: 랜덤 길이의 유효한 summary(10자 이상)를 생성하여
        _parse()가 정상 반환하는지 검증.

        **Validates: Requirements 3.1**
        """
        llm_response = json.dumps({
            "score": round(score, 2),
            "category": category,
            "reason": "Test reason for classification",
            "summary": summary,
            "user_overrides": {},
        })

        service = LLMService()
        result = service._parse(llm_response)

        # 유효한 summary는 strip된 형태로 반환되어야 함
        # (수정 후 _parse()가 summary.strip()을 적용하므로 strip된 값과 비교)
        expected = summary.strip()
        assert result.summary == expected, (
            f"유효한 summary가 변경되었습니다.\n"
            f"입력: {summary!r} (길이: {len(summary)})\n"
            f"기대: {expected!r}\n"
            f"결과: {result.summary!r}"
        )

        # score와 category도 정상 파싱되어야 함
        assert isinstance(result.score, float)
        assert result.category in (ImportanceCategory.NOTIFY, ImportanceCategory.SILENT)


# ---------------------------------------------------------------------------
# Test 3: 규칙 기반 분류 로직 보존 (블랙리스트 → SILENT, 화이트리스트 → NOTIFY)
# **Validates: Requirements 3.2, 3.3**
#
# 현재 코드: _apply_rules()가 블랙리스트/스팸 → SILENT, 화이트리스트 → NOTIFY
# 보존: 수정 후에도 동일하게 동작
# ---------------------------------------------------------------------------

BLACKLIST_DOMAINS = [
    "mail.notion.so",
    "notion.so",
    "promotions.google.com",
    "newsletter.com",
    "marketing.com",
    "no-reply.facebook.com",
]

WHITELIST_DOMAINS = [
    "important-client.com",
    "investor.com",
    "partner-company.com",
]

SPAM_KEYWORDS = [
    "뉴스레터",
    "무료 체험",
    "unsubscribe",
    "webinar",
    "promotional",
]

blacklist_sender_strategy = st.sampled_from(BLACKLIST_DOMAINS).map(
    lambda d: f"noreply@{d}"
)
whitelist_sender_strategy = st.sampled_from(WHITELIST_DOMAINS).map(
    lambda d: f"contact@{d}"
)
spam_keyword_strategy = st.sampled_from(SPAM_KEYWORDS)


class TestRuleBasedClassificationPreservation:
    """규칙 기반 분류 로직이 수정 전후 동일하게 동작해야 함"""

    @given(
        sender=blacklist_sender_strategy,
        subject=english_subject_strategy,
    )
    @settings(max_examples=20)
    def test_blacklist_domain_classified_as_silent(self, sender, subject):
        """
        Property: 블랙리스트 도메인에서 온 메일은 항상 SILENT로 분류되어야 함.

        **Validates: Requirements 3.2**
        """
        event = _make_gmail_event(subject=subject, sender=sender)

        classifier = Classifier()
        config = {
            "blacklist_domains": BLACKLIST_DOMAINS,
            "whitelist_domains": WHITELIST_DOMAINS,
            "spam_keywords": SPAM_KEYWORDS,
            "urgent_keywords": [],
            "score_threshold_notify": 0.50,
        }

        result = classifier._apply_rules(event, config)

        assert result is not None, "블랙리스트 도메인 메일은 규칙에 의해 분류되어야 합니다."
        assert result.category == ImportanceCategory.SILENT, (
            f"블랙리스트 도메인 '{sender}'에서 온 메일이 SILENT가 아닌 "
            f"{result.category}로 분류되었습니다."
        )
        assert result.source == AnalysisSource.RULE, (
            "블랙리스트 분류는 RULE 소스여야 합니다."
        )

    @given(
        sender=whitelist_sender_strategy,
        subject=english_subject_strategy,
    )
    @settings(max_examples=20)
    def test_whitelist_domain_classified_as_notify(self, sender, subject):
        """
        Property: 화이트리스트 도메인에서 온 메일은 항상 NOTIFY로 분류되어야 함.

        **Validates: Requirements 3.3**
        """
        event = _make_gmail_event(subject=subject, sender=sender)

        classifier = Classifier()
        config = {
            "blacklist_domains": BLACKLIST_DOMAINS,
            "whitelist_domains": WHITELIST_DOMAINS,
            "spam_keywords": SPAM_KEYWORDS,
            "urgent_keywords": [],
            "score_threshold_notify": 0.50,
        }

        result = classifier._apply_rules(event, config)

        assert result is not None, "화이트리스트 도메인 메일은 규칙에 의해 분류되어야 합니다."
        assert result.category == ImportanceCategory.NOTIFY, (
            f"화이트리스트 도메인 '{sender}'에서 온 메일이 NOTIFY가 아닌 "
            f"{result.category}로 분류되었습니다."
        )
        assert result.source == AnalysisSource.RULE, (
            "화이트리스트 분류는 RULE 소스여야 합니다."
        )

    @given(
        keyword=spam_keyword_strategy,
        snippet=english_snippet_strategy,
    )
    @settings(max_examples=20)
    def test_spam_keyword_classified_as_silent(self, keyword, snippet):
        """
        Property: 스팸 키워드가 제목에 포함된 메일은 항상 SILENT로 분류되어야 함.

        **Validates: Requirements 3.2**
        """
        subject = f"Special offer: {keyword} inside"
        event = _make_gmail_event(
            subject=subject,
            snippet=snippet,
            sender="random@somecompany.com",
        )

        classifier = Classifier()
        config = {
            "blacklist_domains": BLACKLIST_DOMAINS,
            "whitelist_domains": WHITELIST_DOMAINS,
            "spam_keywords": SPAM_KEYWORDS,
            "urgent_keywords": [],
            "score_threshold_notify": 0.50,
        }

        result = classifier._apply_rules(event, config)

        assert result is not None, "스팸 키워드 포함 메일은 규칙에 의해 분류되어야 합니다."
        assert result.category == ImportanceCategory.SILENT, (
            f"스팸 키워드 '{keyword}'가 포함된 메일이 SILENT가 아닌 "
            f"{result.category}로 분류되었습니다."
        )


# ---------------------------------------------------------------------------
# Test 4: score 기반 NOTIFY/SILENT 판정 보존
# **Validates: Requirements 3.5**
#
# 현재 코드: score < score_threshold_notify → SILENT
# 보존: 수정 후에도 동일하게 동작
# ---------------------------------------------------------------------------

class TestScoreThresholdPreservation:
    """score 기반 NOTIFY/SILENT 판정이 수정 전후 동일하게 동작해야 함"""

    @given(
        score=st.floats(min_value=0.0, max_value=0.49),
        threshold=st.just(0.50),
    )
    @settings(max_examples=30)
    def test_score_below_threshold_classified_as_silent(self, score, threshold):
        """
        Property: score가 score_threshold_notify 미만이면 SILENT로 분류되어야 함.

        **Validates: Requirements 3.5**
        """
        # 임계값 미만의 score를 가진 LLM 결과 생성
        result = AnalysisResult(
            score=score,
            category=ImportanceCategory.NOTIFY,  # LLM이 NOTIFY로 판정했더라도
            reason="Test reason",
            source=AnalysisSource.LLM,
        )

        classifier = Classifier()
        config = {
            "blacklist_domains": [],
            "whitelist_domains": [],
            "spam_keywords": [],
            "urgent_keywords": [],
            "score_threshold_notify": threshold,
        }

        final_result = classifier._apply_thresholds(result, config)

        assert final_result.category == ImportanceCategory.SILENT, (
            f"score {score}이 임계값 {threshold} 미만인데 "
            f"SILENT가 아닌 {final_result.category}로 분류되었습니다."
        )

    @given(
        score=st.floats(min_value=0.50, max_value=1.0),
        threshold=st.just(0.50),
    )
    @settings(max_examples=30)
    def test_score_at_or_above_threshold_classified_as_notify(self, score, threshold):
        """
        Property: score가 score_threshold_notify 이상이면 NOTIFY로 분류되어야 함.

        **Validates: Requirements 3.5**
        """
        result = AnalysisResult(
            score=score,
            category=ImportanceCategory.SILENT,  # LLM이 SILENT로 판정했더라도
            reason="Test reason",
            source=AnalysisSource.LLM,
        )

        classifier = Classifier()
        config = {
            "blacklist_domains": [],
            "whitelist_domains": [],
            "spam_keywords": [],
            "urgent_keywords": [],
            "score_threshold_notify": threshold,
        }

        final_result = classifier._apply_thresholds(result, config)

        assert final_result.category == ImportanceCategory.NOTIFY, (
            f"score {score}이 임계값 {threshold} 이상인데 "
            f"NOTIFY가 아닌 {final_result.category}로 분류되었습니다."
        )


# ---------------------------------------------------------------------------
# Test 5: Bedrock 클라이언트 미초기화 시 안전 반환 보존
# **Validates: Requirements 3.4**
#
# 현재 코드: Bedrock 클라이언트 없음 → SILENT 반환
# 보존: 수정 후에도 동일하게 동작
# ---------------------------------------------------------------------------

class TestFallbackMechanismPreservation:
    """Bedrock 연결 실패 시 안전 반환 메커니즘이 동작해야 함"""

    @given(
        subject=english_subject_strategy,
        snippet=english_snippet_strategy,
    )
    @settings(max_examples=10)
    def test_fallback_returns_silent_when_all_services_fail(self, subject, snippet):
        """
        Property: Bedrock 클라이언트가 없으면 SILENT로 분류되어야 함.

        **Validates: Requirements 3.4**
        """
        event = _make_gmail_event(subject=subject, snippet=snippet)

        service = LLMService()
        # 모든 클라이언트를 None으로 설정하여 호출 불가하도록
        service.client = None
        service.tw_client = None

        result = service.analyze_email(event)

        # 서비스 실패 시 SILENT로 분류되어야 함
        assert result.category == ImportanceCategory.SILENT, (
            f"LLM 서비스 실패 시 SILENT가 아닌 {result.category}로 분류되었습니다."
        )
        assert result.source == AnalysisSource.LLM, (
            "폴백 결과의 소스는 LLM이어야 합니다."
        )

    @given(
        subject=english_subject_strategy,
        snippet=english_snippet_strategy,
    )
    @settings(max_examples=10)
    def test_bedrock_exception_returns_notify_for_safety(self, subject, snippet):
        """
        Property: Bedrock 호출 중 예외 발생 시 NOTIFY로 분류되어야 함 (중요 메일 누락 방지).

        **Validates: Requirements 3.4**
        """
        event = _make_gmail_event(subject=subject, snippet=snippet)

        service = LLMService()
        # TW 비활성, Bedrock client가 있지만 호출 시 예외 발생
        service.tw_client = None
        service.client = MagicMock()
        service.client.messages.create.side_effect = Exception("Bedrock API error")

        result = service.analyze_email(event)

        # Bedrock 호출 예외 시 NOTIFY 반환 (안전을 위해 알림 전송)
        assert result.category == ImportanceCategory.NOTIFY, (
            f"Bedrock 호출 예외 시 NOTIFY가 아닌 {result.category}로 분류되었습니다."
        )
