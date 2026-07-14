"""
Unit tests for Gmail body text extraction (Task 3.2)

Tests _extract_body_text(), _decode_base64(), _strip_html_tags(),
and _parse_gmail_message() with format='full' payloads.

**Validates: Requirements 2.2**
"""
import base64
import sys
import os
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock googleapiclient if not installed in test env
if "googleapiclient" not in sys.modules:
    sys.modules["googleapiclient"] = MagicMock()
    sys.modules["googleapiclient.discovery"] = MagicMock()
    sys.modules["googleapiclient.errors"] = MagicMock()

from app.services.gmail_service import GmailService


@pytest.fixture
def service():
    """GmailService 인스턴스 (API 호출 없이 파싱 메서드만 테스트)."""
    svc = object.__new__(GmailService)
    return svc


def _b64(text: str) -> str:
    """Helper: UTF-8 텍스트를 URL-safe base64로 인코딩."""
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii")


# ---------------------------------------------------------------------------
# _decode_base64
# ---------------------------------------------------------------------------

class TestDecodeBase64:
    def test_decodes_utf8_text(self):
        original = "Hello, 안녕하세요!"
        assert GmailService._decode_base64(_b64(original)) == original

    def test_handles_missing_padding(self):
        original = "test"
        encoded = base64.urlsafe_b64encode(original.encode()).decode().rstrip("=")
        assert GmailService._decode_base64(encoded) == original


# ---------------------------------------------------------------------------
# _strip_html_tags
# ---------------------------------------------------------------------------

class TestStripHtmlTags:
    def test_removes_simple_tags(self):
        html = "<p>Hello <b>world</b></p>"
        result = GmailService._strip_html_tags(html)
        assert "Hello" in result
        assert "world" in result
        assert "<b>" not in result

    def test_converts_br_to_newline(self):
        html = "Line1<br>Line2<br/>Line3"
        result = GmailService._strip_html_tags(html)
        assert "Line1\nLine2\nLine3" == result

    def test_removes_style_and_script(self):
        html = "<style>body{color:red}</style><script>alert(1)</script><p>Content</p>"
        result = GmailService._strip_html_tags(html)
        assert "Content" in result
        assert "color" not in result
        assert "alert" not in result

    def test_decodes_html_entities(self):
        html = "A &amp; B &lt; C &gt; D &nbsp; E"
        result = GmailService._strip_html_tags(html)
        assert "A & B < C > D" in result


# ---------------------------------------------------------------------------
# _extract_body_text
# ---------------------------------------------------------------------------

class TestExtractBodyText:
    def test_single_part_plain_text(self, service):
        payload = {
            "mimeType": "text/plain",
            "body": {"data": _b64("Plain body content")},
        }
        assert service._extract_body_text(payload) == "Plain body content"

    def test_single_part_html(self, service):
        payload = {
            "mimeType": "text/html",
            "body": {"data": _b64("<p>HTML body</p>")},
        }
        result = service._extract_body_text(payload)
        assert "HTML body" in result
        assert "<p>" not in result

    def test_multipart_prefers_plain(self, service):
        payload = {
            "mimeType": "multipart/alternative",
            "parts": [
                {"mimeType": "text/plain", "body": {"data": _b64("Plain version")}},
                {"mimeType": "text/html", "body": {"data": _b64("<b>HTML version</b>")}},
            ],
        }
        assert service._extract_body_text(payload) == "Plain version"

    def test_multipart_falls_back_to_html(self, service):
        payload = {
            "mimeType": "multipart/alternative",
            "parts": [
                {"mimeType": "text/plain", "body": {"data": ""}},
                {"mimeType": "text/html", "body": {"data": _b64("<b>HTML only</b>")}},
            ],
        }
        result = service._extract_body_text(payload)
        assert "HTML only" in result

    def test_nested_multipart(self, service):
        payload = {
            "mimeType": "multipart/mixed",
            "parts": [
                {
                    "mimeType": "multipart/alternative",
                    "parts": [
                        {"mimeType": "text/plain", "body": {"data": _b64("Nested plain")}},
                        {"mimeType": "text/html", "body": {"data": _b64("<p>Nested HTML</p>")}},
                    ],
                },
                {"mimeType": "application/pdf", "body": {"data": ""}},
            ],
        }
        assert service._extract_body_text(payload) == "Nested plain"

    def test_empty_payload_returns_none(self, service):
        payload = {"mimeType": "text/plain", "body": {}}
        assert service._extract_body_text(payload) is None

    def test_korean_body(self, service):
        korean_text = "안녕하세요, 프로젝트 일정 변경 안내드립니다."
        payload = {
            "mimeType": "text/plain",
            "body": {"data": _b64(korean_text)},
        }
        assert service._extract_body_text(payload) == korean_text


# ---------------------------------------------------------------------------
# _parse_gmail_message with body_text
# ---------------------------------------------------------------------------

class TestParseGmailMessageWithBody:
    def test_includes_body_text_in_raw_data(self, service):
        body_content = "This is the full email body for context."
        message = {
            "id": "msg123",
            "snippet": "This is the snippet",
            "internalDate": "1700000000000",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Test Subject"},
                    {"name": "From", "value": "sender@example.com"},
                    {"name": "Message-ID", "value": "<test@example.com>"},
                ],
                "mimeType": "text/plain",
                "body": {"data": _b64(body_content)},
            },
        }
        event = service._parse_gmail_message(message, "owner@example.com")
        assert event is not None
        assert event.raw_data["body_text"] == body_content
        assert event.raw_data["snippet"] == "This is the snippet"
        assert event.raw_data["gmail_id"] == "msg123"

    def test_preserves_metadata_fields(self, service):
        message = {
            "id": "msg456",
            "snippet": "A snippet",
            "internalDate": "1700000000000",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Important Subject"},
                    {"name": "From", "value": "John <john@example.com>"},
                    {"name": "To", "value": "owner@example.com"},
                    {"name": "Message-ID", "value": "<msg456@example.com>"},
                ],
                "mimeType": "text/plain",
                "body": {"data": _b64("Body text here")},
            },
        }
        event = service._parse_gmail_message(message, "owner@example.com")
        assert event is not None
        assert event.subject == "Important Subject"
        assert event.sender == "john@example.com"
        assert event.owner == "owner@example.com"
        assert event.event_type == "UNREAD"

    def test_no_body_text_when_empty(self, service):
        message = {
            "id": "msg789",
            "snippet": "Just a snippet",
            "internalDate": "1700000000000",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "No Body"},
                    {"name": "From", "value": "sender@example.com"},
                ],
                "mimeType": "text/plain",
                "body": {},
            },
        }
        event = service._parse_gmail_message(message, "owner@example.com")
        assert event is not None
        assert "body_text" not in event.raw_data
        assert event.raw_data["snippet"] == "Just a snippet"
