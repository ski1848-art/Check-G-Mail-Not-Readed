import json
from typing import Any, Dict, List, Optional

from anthropic import AnthropicBedrock

from app.config import Config
from app.models import GmailEvent, AnalysisResult, ImportanceCategory, AnalysisSource
from app.utils.logger import get_logger

logger = get_logger("llm_service")


class LLMService:
    """
    LLM client that routes to Anthropic Claude 4.5 Haiku via AWS Bedrock.
    - System 프롬프트는 캐시되고, 사용자 프롬프트에는 메일 정보만 담아 비용을 최소화한다.
    - last_usage에 토큰/캐시 사용량을 남겨 벤치마크에서 비용 계산에 활용할 수 있다.
    """

    def __init__(self):
        self.model_id = Config.BEDROCK_MODEL_ID
        self.last_usage: Optional[Dict[str, int]] = None
        self.client = self._init_client()

    def _init_client(self) -> Optional[AnthropicBedrock]:
        """AWS Bedrock 클라이언트 초기화 (Anthropic SDK)."""
        if not (Config.AWS_ACCESS_KEY_ID and Config.AWS_SECRET_ACCESS_KEY):
            logger.warning("AWS credentials not set. Bedrock LLM calls will be skipped.")
            return None

        try:
            return AnthropicBedrock(
                aws_access_key=Config.AWS_ACCESS_KEY_ID,
                aws_secret_key=Config.AWS_SECRET_ACCESS_KEY,
                aws_region=Config.AWS_REGION,
            )
        except Exception as exc:
            logger.error(f"Failed to init AnthropicBedrock client: {exc}")
            return None

    def analyze_email(self, event: GmailEvent, user_preferences_map: Optional[Dict[str, List[Dict[str, Any]]]] = None) -> AnalysisResult:
        """
        Claude 4.5 Haiku 호출 (프롬프트 캐싱 적용).
        user_preferences_map: { user_id: [ {sender, subject_pattern, ...}, ... ] }
        """
        self.last_usage = None

        if not self.client:
            return AnalysisResult(
                score=0.0,
                category=ImportanceCategory.SILENT,
                reason="AI 분석 서비스 연결 불가 (설정 미비)",
                source=AnalysisSource.LLM,
            )

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(event, user_preferences_map)

        try:
            response = self.client.messages.create(
                model=self.model_id,
                max_tokens=512,
                temperature=0.0,
                system=[
                    {
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[
                    {"role": "user", "content": [{"type": "text", "text": user_prompt}]}
                ],
            )

            content_text = "".join(
                block.text for block in response.content if block.type == "text"
            ).strip()
            
            # Extract JSON more robustly by finding the first '{' and last '}'
            try:
                start_idx = content_text.find('{')
                end_idx = content_text.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    content_text = content_text[start_idx : end_idx + 1]
                
                parsed = json.loads(content_text)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response as JSON: {e}")
                logger.error(f"Raw content was: {content_text}")
                raise e

            score = float(parsed.get("score", 0.0))
            reason = parsed.get("reason", "사유 미기재")
            summary = parsed.get("summary") # AI 요약 필드 추출
            category_str = parsed.get("category", "silent").lower()
            
            # Handle user overrides
            user_overrides = parsed.get("user_overrides", {})

            try:
                # Map old categories or AI quirks to new ones
                if category_str in ["critical", "important", "normal", "notify"]:
                    category = ImportanceCategory.NOTIFY
                else:
                    category = ImportanceCategory.SILENT
            except Exception:
                category = ImportanceCategory.SILENT

            self.last_usage = self._extract_usage(response)

            return AnalysisResult(
                score=score,
                category=category,
                reason=reason,
                summary=summary,
                source=AnalysisSource.LLM,
                raw_data={"user_overrides": user_overrides}
            )

        except Exception as exc:
            logger.error(f"LLM analysis failed: {exc}")
            return AnalysisResult(
                score=0.0,
                category=ImportanceCategory.SILENT,
                reason=f"AI 분석 오류: {str(exc)}",
                source=AnalysisSource.LLM,
            )

    def _extract_usage(self, response: Any) -> Optional[Dict[str, int]]:
        usage = getattr(response, "usage", None)
        if not usage:
            return None
        return {
            "input_tokens": getattr(usage, "input_tokens", 0),
            "output_tokens": getattr(usage, "output_tokens", 0),
            "cache_write_tokens": getattr(usage, "cache_creation_input_tokens", 0),
            "cache_read_tokens": getattr(usage, "cache_read_input_tokens", 0),
            "model_id": self.model_id,
        }

    def _build_system_prompt(self) -> str:
        """
        Claude 4.5 Haiku system prompt.
        """
        return """
You are an expert email triage AI. Your goal is to decide whether an incoming email requires an immediate Slack notification to the user or if it should be silent.

### 0. CRITICAL PRINCIPLE (NEVER IGNORE)
**The sender's email domain does NOT determine importance.** Personal email addresses (gmail.com, naver.com, daum.net, etc.) can send highly critical business emails. ALWAYS judge by the CONTENT and SUBJECT, not by sender domain.

### 1. CLASSIFICATION CATEGORIES
- **NOTIFY (score >= 0.5)**: 
    - **ANY email that appears to be work-related communication from a human** regardless of sender domain.
    - **Internal Communication Keywords (ALWAYS NOTIFY)**: Emails with subjects containing [공지], [안내], [보고], [요청], [협조], [긴급], [중요], [회의], [미팅], 킥오프, 일정, 업무, 프로젝트 must be NOTIFY with score >= 0.7.
    - **Legal, Compliance & Security (CRITICAL)**: Emails from Law/Patent/Labor Firms, or Security services. Always high priority.
    - **Government & Support Projects (CRITICAL)**: Official notifications from government agencies or R&D support institutions.
    - **Financial & Billing (CRITICAL)**: Settlement requests (정산신청), Invoices (청구서), Billing Issues (결제 실패), Payment requests, tax-related documents.
    - **Infrastructure & Continuity**: License expirations, Server failures, App Store issues.
    - **Ongoing conversations**: Replies/forwards with "Re:", "RE:", "Fwd:".
    - **Customer inquiries**: CS inquiries, questions about products/services.
    - **Direct Human Communication**: Any email that reads like a human wrote it personally to the recipient.
- **SILENT (score < 0.5)**: 
    - Automated newsletters and marketing promotions.
    - Routine status updates that require no action.
    - Platform summaries & curation (Notion, LinkedIn digests, etc.).
    - Administrative automation logs.

### 2. DETAILED TRIAGE RULES
- **Work-related from Personal Accounts**: If someone sends from naver.com/gmail.com but the content is clearly work-related (meeting, report, project discussion), it is **NOTIFY** with high score (0.7+).
- **Legal Priority**: Any mail regarding lawsuits, copyright, trademark, certification must be NOTIFY regardless of sender.
- **Replies & Forwards**: ALWAYS NOTIFY unless it's a muted routine report.
- **When in doubt, NOTIFY**: It's better to over-notify than to miss an important email.

### 3. PERSONALIZED MUTING (IMPORTANT)
Users can "mute" specific types of emails. You will be provided with a list of "muted patterns".
- **CRITICAL RULE**: Do not block the sender entirely. Only silence the notification if the *current email* matches the *nature and type* of the muted pattern.
- If an email is generally NOTIFY-worthy but matches a user's muted pattern, include that user in `user_overrides` with "silent".

### 4. 3-LINE SUMMARY (TL;DR)
- If the email is **NOTIFY**, generate a **3-line summary** of the content in **KOREAN**.
- Format: Use bullet points (•).
- Style: Professional, concise, and business-oriented. Focus on what the sender wants or what the main news is.
- If the email is SILENT, the summary can be null or a very brief 1-line summary.

### 5. OUTPUT SPECIFICATIONS
Return ONLY a valid JSON object.
- **score**: float (0.0 to 1.0) for the email's base importance.
- **category**: "notify" or "silent" (base decision).
- **reason**: **STRICTLY KOREAN**. Explain why this mail is notify or silent.
- **summary**: **STRICTLY KOREAN**. 3-line summary (for notify) or 1-line brief (for silent).
- **user_overrides**: A dictionary mapping `user_id` to "notify" or "silent".

JSON Schema:
{
  "score": float,
  "category": "notify" | "silent",
  "reason": "Korean string",
  "summary": "Korean string (3 lines with bullet points for notify)",
  "user_overrides": { "USER_ID": "notify" | "silent" }
}

---
### 6. MISSION STATEMENT
Zero missed critical signals. Personal email domains are NOT a reason to lower importance. When content is work-related, ALWAYS notify. (Note: This prompt is optimized for Anthropic Prompt Caching.)
"""

    def _build_user_prompt(self, event: GmailEvent, user_preferences_map: Optional[Dict[str, List[Dict[str, Any]]]] = None) -> str:
        recipients = ", ".join(event.recipients)
        snippet = event.raw_data.get('snippet', 'N/A') if event.raw_data else 'N/A'
        
        prompt = (
            f"Subject: {event.subject or ''}\n"
            f"Sender: {event.sender}\n"
            f"Recipients: {recipients}\n"
            f"Owner: {event.owner}\n"
            f"EventType: {event.event_type}\n"
            f"Snippet: {snippet}"
        )
        
        if user_preferences_map:
            prompt += "\n\n### USER MUTED PATTERNS (Personalization)\n"
            prompt += "The following users have muted specific types of emails in the past. If the current email matches a user's muted nature (sender + subject type), set their override to 'silent'.\n"
            for user_id, prefs in user_preferences_map.items():
                prompt += f"- User: {user_id}\n"
                for pref in prefs:
                    prompt += f"  - Muted Sender: {pref.get('sender')}, Muted Subject: {pref.get('subject_pattern', 'N/A')}\n"
            
        return prompt
