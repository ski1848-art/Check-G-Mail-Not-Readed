"""normalize_mrkdwn 단위 테스트.

AI 요약에 섞여 나오는 표준 마크다운 장식(**굵게**, # 제목, ~~취소선~~)이 Slack에서
기호 그대로 노출되던 버그(운영 관찰: Semrush 순위 알림 요약)의 회귀 방지.
슬랙 위장 링크 injection 심층방어(< > & 이스케이프)도 함께 검증한다.
"""
from app.services.slack_service import normalize_mrkdwn


class TestBoldNormalization:
    def test_double_star_to_single(self):
        assert normalize_mrkdwn("**굵게**") == "*굵게*"

    def test_multiple_bold_in_line(self):
        assert normalize_mrkdwn("**A** and **B**") == "*A* and *B*"

    def test_single_star_preserved(self):
        # 이미 Slack 형식인 별표 하나는 손상되지 않아야 함
        assert normalize_mrkdwn("*이미굵게*") == "*이미굵게*"

    def test_arithmetic_star_preserved(self):
        assert normalize_mrkdwn("3*4=12") == "3*4=12"

    def test_unmatched_stars_do_not_crash(self):
        # 짝이 맞지 않는 ** 는 예외 없이 통과(원문 보존)해야 함
        for bad in ("**a", "a**", "**a**b**"):
            normalize_mrkdwn(bad)  # no exception


class TestHeadingRemoval:
    def test_heading_marker_removed_text_kept(self):
        assert normalize_mrkdwn("# 제목\n• 내용") == "제목\n• 내용"

    def test_multi_level_heading(self):
        assert normalize_mrkdwn("### 소제목") == "소제목"

    def test_bullet_preserved(self):
        assert normalize_mrkdwn("• 첫줄\n• 둘째줄") == "• 첫줄\n• 둘째줄"


class TestStrikethrough:
    def test_double_tilde_to_single(self):
        assert normalize_mrkdwn("~~취소~~") == "~취소~"


class TestUnderscoreNotConverted:
    def test_dunder_dev_token_kept(self):
        # __init__ 등 개발 용어는 볼드로 오변환되지 않아야 함
        assert normalize_mrkdwn("__init__ 이 호출됨") == "__init__ 이 호출됨"

    def test_snake_case_kept(self):
        assert normalize_mrkdwn("foo__bar__baz") == "foo__bar__baz"


class TestSlackInjectionDefense:
    def test_angle_link_neutralized(self):
        # 위장 링크(<url|문구>)가 실제 링크로 렌더되지 못하도록 이스케이프
        out = normalize_mrkdwn("클릭 <https://evil.com|긴급 확인>")
        assert "<https" not in out
        assert "&lt;" in out and "&gt;" in out

    def test_ampersand_escaped(self):
        assert normalize_mrkdwn("A & B") == "A &amp; B"


class TestSafetyGuards:
    def test_empty_string(self):
        assert normalize_mrkdwn("") == ""

    def test_none_returns_none(self):
        assert normalize_mrkdwn(None) is None

    def test_plain_text_unchanged(self):
        # 장식/특수문자 없는 순수 요약은 그대로(양끝 공백만 정리)
        s = "• 오늘 매출 15% 증가\n• 금요일까지 피드백 요청"
        assert normalize_mrkdwn(s) == s

    def test_realistic_semrush_summary(self):
        # 운영에서 실제로 문제됐던 형태 (제목 + 볼드 라벨)
        raw = (
            "# SNS헬프 순위 변동 알림 요약\n"
            "• **프로젝트**: SNS헬프 1개 키워드 상위 10위 진입\n"
            "• **발신처**: Semrush 순위 추적 시스템"
        )
        out = normalize_mrkdwn(raw)
        assert "**" not in out          # 이중 별표 사라짐
        assert not out.startswith("#")  # 제목 마크 사라짐
        assert "*프로젝트*" in out       # 슬랙식 굵게로 변환
