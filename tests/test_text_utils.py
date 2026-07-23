"""strip_quoted_reply 단위 테스트.

회신 메일에 누적되는 이전 대화 인용이 요약에 혼입되던 문제(운영 관찰:
Kaspersky 기술지원 스레드의 옛 대화가 슬랙 요약 2번째 줄에 섞임)의 회귀 방지.
"""
from app.utils.text_utils import strip_quoted_reply


class TestQuoteBoundaryCut:
    def test_outlook_from_sent_header(self):
        raw = ("새로 드리는 질문입니다. 확인 부탁드립니다.\n\n"
               "From: 홍길동 <a@b.com>\nSent: Monday\nTo: c@d.com\n인용된 옛 내용")
        out = strip_quoted_reply(raw)
        assert "옛 내용" not in out
        assert "새로 드리는 질문" in out

    def test_original_message_marker(self):
        raw = "이번에 전달드리는 새 본문 내용입니다.\n\n-----Original Message-----\n옛날 대화 내용"
        out = strip_quoted_reply(raw)
        assert "옛날 대화" not in out
        assert "새 본문" in out

    def test_gmail_korean_wrote_header(self):
        raw = ("이번에 드리는 말씀입니다. 확인 부탁드립니다.\n\n"
               "2026년 7월 21일 (화) 오후 2:40, 변홍주 <x@y.com>님이 작성:\n> 옛 인용 라인")
        out = strip_quoted_reply(raw)
        assert "옛 인용" not in out
        assert "이번에 드리는 말씀" in out

    def test_gmail_english_wrote(self):
        raw = "My new message here, please review it.\n\nOn Mon, Jul 21 2026, Hong <x@y.com> wrote:\nold quoted text"
        out = strip_quoted_reply(raw)
        assert "old quoted" not in out
        assert "new message" in out

    def test_quote_gt_lines(self):
        raw = "새 내용이 충분히 길게 여기 있습니다.\n> 옛 인용 라인\n> 또 다른 인용"
        out = strip_quoted_reply(raw)
        assert "옛 인용" not in out
        assert "새 내용" in out


class TestSafetyGuards:
    def test_no_marker_returns_original(self):
        raw = "인용이 전혀 없는 순수한 새 메일 본문입니다."
        assert strip_quoted_reply(raw) == raw

    def test_marker_at_start_keeps_original(self):
        # 마커가 사실상 맨 앞이면 과다 절단 방지 위해 원문 유지 → 내용 보존
        raw = "From: a@b.com\nSent: now\n실제 본문 내용이 여기 있습니다"
        out = strip_quoted_reply(raw)
        assert "실제 본문 내용" in out

    def test_none_returns_none(self):
        assert strip_quoted_reply(None) is None

    def test_empty_returns_empty(self):
        assert strip_quoted_reply("") == ""


class TestRealisticKasperskyThread:
    def test_quoted_previous_mail_removed(self):
        # 운영에서 실제 문제됐던 형태 (우명기 새 질문 + 변홍주 옛 메일 인용)
        raw = (
            "안녕하세요. KCC 정보통신 우명기입니다.\n"
            "분석하는 과정에서 아래 문의가 있었습니다:\n"
            "1. 재시작 후 CPU 사용량이 바로 증가하는지 확인 부탁\n"
            "2. 문제가 발생하는 구성요소 확인 부탁\n"
            "3. 네트워크 에이전트 중지 시 증상이 사라지는지 확인 부탁\n"
            "회신 부탁드립니다.\n\n"
            "From: 변홍주 <ski1848@hotseller.co.kr>\n"
            "Sent: Tuesday, July 21, 2026 2:40 PM\n"
            "To: 우명기 <mkwoo@kcc.co.kr>\n"
            "앞서 전달드린 collect.sh 진단 파일에는 원본 Trace 로그가 포함되지 않아 별도 전달드립니다.\n"
        )
        out = strip_quoted_reply(raw)
        assert "Trace" not in out          # 인용된 옛 내용 제거됨
        assert "collect.sh" not in out
        assert "우명기" in out and "재시작" in out  # 새 내용은 보존
        assert len(out) < 300              # 5000자대 → 수백 자로 축소


class TestFalsePositiveGuard:
    def test_korean_title_with_jaksung_not_cut(self):
        # "2024년 사업계획 작성:" 같은 정상 제목을 인용 경계로 오탐하면 안 됨
        raw = "자료 첨부드립니다.\n2024년 사업계획 작성:\n항목1, 항목2, 항목3 이어집니다."
        out = strip_quoted_reply(raw)
        assert "항목3" in out


class TestStrongMarkerShortReply:
    def test_short_reply_quote_removed(self):
        # 새 내용이 짧아도(<15자) 강한 마커(이메일 헤더)면 인용 제거되어야 함
        raw = "확인했습니다.\n\nFrom: A <a@b.com>\nSent: Mon\nTo: x\n옛날 긴 대화 내용"
        out = strip_quoted_reply(raw)
        assert "옛날" not in out
        assert "확인했습니다" in out


class TestMorePatterns:
    def test_korean_outlook_block(self):
        raw = "새 문의 내용이 충분히 깁니다.\n보낸 사람: 홍길동 <a@b.com>\n보낸 날짜: 월요일\n옛 인용 내용"
        out = strip_quoted_reply(raw)
        assert "옛 인용" not in out
        assert "새 문의" in out

    def test_korean_original_message(self):
        raw = "이번에 전달드리는 새 본문입니다.\n-----원본 메시지-----\n옛 대화 내용"
        out = strip_quoted_reply(raw)
        assert "옛 대화" not in out

    def test_underscore_divider(self):
        raw = "새 내용이 충분히 길게 여기 있습니다.\n" + "_" * 30 + "\nFrom: x\n옛 대화 내용"
        out = strip_quoted_reply(raw)
        assert "옛 대화" not in out


class TestReDoSSafety:
    def test_large_whitespace_run_is_fast(self):
        import time
        s = "2020년작성" + " " * 200000 + "x"
        t = time.perf_counter()
        strip_quoted_reply(s)
        assert time.perf_counter() - t < 0.2  # 상수 시간(입력 크기 무관)

    def test_large_dash_run_is_fast(self):
        import time
        s = "-" * 200000 + " Original Messagex"
        t = time.perf_counter()
        strip_quoted_reply(s)
        assert time.perf_counter() - t < 0.2
