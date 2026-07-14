"""
Bug Condition Exploration Property Tests — 한국어 메일 요약 품질 버그 재현

이 테스트는 수정 전 코드에서 버그를 재현하는 반례를 확인합니다.
수정 전 코드에서는 FAIL이 예상됩니다 (버그 존재 증명).
수정 후 코드에서는 PASS가 예상됩니다 (버그 수정 확인).

**Validates: Requirements 1.1, 1.2, 1.3, 1.4**
"""
import json
import re
import sys
import os
from datetime import datetime

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import GmailEvent, AnalysisResult, ImportanceCategory, AnalysisSource
from app.services.llm_service import LLMService


# ---------------------------------------------------------------------------
# Strategies: 한국어 메일 이벤트 생성
# ---------------------------------------------------------------------------

KOREAN_SUBJECTS = [
    "프로젝트 일정 변경 안내",
    "회의록 공유드립니다",
    "긴급: 서버 장애 발생",
    "월간 보고서 검토 요청",
    "신규 입사자 환영합니다",
    "계약서 수정 요청",
    "출장 일정 확인 부탁드립니다",
]

KOREAN_SNIPPETS = [
    "안녕하세요, 프로젝트 일정이 변경되었습니다. 확인 부탁드립니다.",
    "금주 회의록을 공유드립니다. 첨부 파일을 확인해 주세요.",
    "서버 장애가 발생하여 긴급 대응이 필요합니다.",
    "월간 보고서를 검토해 주시기 바랍니다.",
    "신규 입사자 OOO님을 환영합니다.",
]

SHORT_SNIPPETS = [
    "확인",
    "OK",
    "감사합니다",
    "네",
    "알겠습니다",
]


korean_subject_strategy = st.sampled_from(KOREAN_SUBJECTS)
korean_snippet_strategy = st.sampled_from(KOREAN_SNIPPETS)
short_snippet_strategy = st.sampled_from(SHORT_SNIPPETS)


def _make_gmail_event(
    subject: str = "테스트 메일",
    snippet: str = "테스트 스니펫입니다.",
    body_text: str = None,
    sender: str = "sender@example.com",
) -> GmailEvent:
    """테스트용 GmailEvent 생성 헬퍼"""
    raw_data = {"snippet": snippet, "gmail_id": "test_msg_001"}
    if body_text is not None:
        raw_data["body_text"] = body_text
    return GmailEvent(
        timestamp=datetime.now(),
        message_id="test_msg_001",
        subject=subject,
        sender=sender,
        recipients=["recipient@example.com"],
        owner="owner@example.com",
        event_type="RECEIVE",
        raw_data=raw_data,
    )


def _contains_korean(text: str) -> bool:
    """텍스트에 한국어가 포함되어 있는지 확인"""
    if not text:
        return False
    return bool(re.search(r"[\uac00-\ud7af\u1100-\u11ff\u3130-\u318f\ua960-\ua97f\ud7b0-\ud7ff]", text))


# ---------------------------------------------------------------------------
# Test 1: _build_system_prompt() 한국어 요약 지시 검증
# **Validates: Requirements 1.1**
#
# 현재 코드: "summary": "Korean" 한 단어뿐
# 수정 후: 구체적 한국어 요약 지시 (형식, 길이, 품질 기준) 포함
# ---------------------------------------------------------------------------

class TestSystemPromptKoreanInstruction:
    """시스템 프롬프트에 한국어 요약 형식/품질 지시가 구체적으로 포함되어야 함"""

    @given(subject=korean_subject_strategy)
    @settings(max_examples=10)
    def test_system_prompt_contains_detailed_korean_instructions(self, subject):
        """
        Property: 시스템 프롬프트에 한국어 요약에 대한 구체적 지시가 포함되어야 함.
        "Korean" 한 단어만으로는 불충분 — 요약 형식, 길이, 품질 기준이 명시되어야 함.

        **Validates: Requirements 1.1**
        """
        service = LLMService()
        prompt = service._build_system_prompt()

        # 시스템 프롬프트에 한국어 요약에 대한 구체적 지시가 있어야 함
        # 단순히 "Korean" 한 단어가 아닌, 요약 형식/품질에 대한 상세 지시
        korean_instruction_patterns = [
            r"한국어",           # 한국어로 요약하라는 지시
            r"3줄|세 줄|3-line", # 3줄 이내 요약 형식
            r"요약",             # 요약에 대한 지시
        ]

        has_detailed_korean_instruction = any(
            re.search(pattern, prompt) for pattern in korean_instruction_patterns
        )

        assert has_detailed_korean_instruction, (
            f"시스템 프롬프트에 한국어 요약에 대한 구체적 지시가 없습니다.\n"
            f"현재 프롬프트: {prompt[:200]}...\n"
            f"'Korean' 한 단어만 있고, 요약 형식/길이/품질 기준이 명시되지 않았습니다."
        )


# ---------------------------------------------------------------------------
# Test 2: _build_user_prompt() 본문 컨텍스트 포함 검증
# **Validates: Requirements 1.2**
#
# 현재 코드: snippet만 전달, body_text 미포함
# 수정 후: body_text가 raw_data에 있으면 프롬프트에 포함
# ---------------------------------------------------------------------------

class TestUserPromptBodyContext:
    """사용자 프롬프트에 메일 본문(body_text)이 포함되어야 함"""

    @given(
        subject=korean_subject_strategy,
        snippet=korean_snippet_strategy,
    )
    @settings(max_examples=10)
    def test_user_prompt_includes_body_text_when_available(self, subject, snippet):
        """
        Property: raw_data에 body_text가 있으면 사용자 프롬프트에 포함되어야 함.
        현재 코드는 snippet만 전달하고 body_text를 무시함.

        **Validates: Requirements 1.2**
        """
        body_text = "이것은 메일 본문입니다. 프로젝트 일정이 다음과 같이 변경되었습니다."
        event = _make_gmail_event(
            subject=subject,
            snippet=snippet,
            body_text=body_text,
        )

        service = LLMService()
        prompt = service._build_user_prompt(event)

        # body_text가 프롬프트에 포함되어야 함
        assert "body" in prompt.lower() or body_text in prompt, (
            f"사용자 프롬프트에 메일 본문(body_text)이 포함되지 않았습니다.\n"
            f"현재 프롬프트: {prompt}\n"
            f"snippet만 전달되고 body_text가 누락되었습니다."
        )


# ---------------------------------------------------------------------------
# Test 3: _parse() 빈 문자열 summary 검증
# **Validates: Requirements 1.4**
#
# 현재 코드: 빈 문자열 "" summary를 그대로 반환
# 수정 후: 빈 문자열은 None으로 변환
# ---------------------------------------------------------------------------

class TestParseEmptySummaryFiltering:
    """_parse()가 빈 문자열 summary를 None으로 변환해야 함"""

    @given(
        score=st.floats(min_value=0.0, max_value=1.0),
        category=st.sampled_from(["notify", "silent"]),
    )
    @settings(max_examples=10)
    def test_parse_converts_empty_summary_to_none(self, score, category):
        """
        Property: _parse()가 빈 문자열 "" summary를 None으로 변환해야 함.
        현재 코드는 빈 문자열을 그대로 반환하여 Slack 알림에 빈 요약이 표시됨.

        **Validates: Requirements 1.4**
        """
        llm_response = json.dumps({
            "score": round(score, 2),
            "category": category,
            "reason": "테스트 사유",
            "summary": "",
            "user_overrides": {},
        })

        service = LLMService()
        result = service._parse(llm_response)

        # 빈 문자열 summary는 None으로 변환되어야 함
        assert result.summary is None, (
            f"_parse()가 빈 문자열 summary를 그대로 반환했습니다.\n"
            f"result.summary = {result.summary!r}\n"
            f"빈 문자열은 None으로 변환되어야 합니다."
        )


# ---------------------------------------------------------------------------
# Test 4: _parse() 10자 미만 짧은 summary 검증
# **Validates: Requirements 1.4**
#
# 현재 코드: "요약" 같은 짧은 summary를 그대로 반환
# 수정 후: 10자 미만은 None으로 변환
# ---------------------------------------------------------------------------

class TestParseShortSummaryFiltering:
    """_parse()가 10자 미만 summary를 None으로 변환해야 함"""

    @given(
        score=st.floats(min_value=0.0, max_value=1.0),
        category=st.sampled_from(["notify", "silent"]),
        short_summary=st.sampled_from(["요약", "Korean", "OK", "확인", "N/A", "없음", "test", "hi"]),
    )
    @settings(max_examples=10)
    def test_parse_converts_short_summary_to_none(self, score, category, short_summary):
        """
        Property: _parse()가 10자 미만 summary를 None으로 변환해야 함.
        현재 코드는 "요약" 같은 무의미한 짧은 요약을 그대로 반환함.

        **Validates: Requirements 1.4**
        """
        assume(len(short_summary) < 10)

        llm_response = json.dumps({
            "score": round(score, 2),
            "category": category,
            "reason": "테스트 사유",
            "summary": short_summary,
            "user_overrides": {},
        })

        service = LLMService()
        result = service._parse(llm_response)

        # 10자 미만 summary는 None으로 변환되어야 함
        assert result.summary is None, (
            f"_parse()가 10자 미만 summary '{short_summary}'(길이: {len(short_summary)})를 "
            f"그대로 반환했습니다.\n"
            f"result.summary = {result.summary!r}\n"
            f"10자 미만 요약은 무의미하므로 None으로 변환되어야 합니다."
        )
