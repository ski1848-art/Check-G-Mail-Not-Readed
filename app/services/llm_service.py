"""
llm_service.py - AI(LLM) 이메일 분석 서비스

[호출 우선순위]
  1. Token-Watcher v2 (LLM 프록시 게이트웨이) — pass_through_body 방식
  2. AWS Bedrock 직접 호출 (AnthropicBedrock SDK) — Token-Watcher 장애 시 폴백

[AI 모델]
  Claude Haiku 4.5 (us.anthropic.claude-haiku-4-5-20251001-v1:0)

[프롬프트 구조]
  - System: "이메일 분류 AI. JSON만 반환. notify/silent 판단 기준 설명"
  - User: 메일 제목/발신자/수신자/스니펫 + 사용자별 차단 패턴(MUTED PATTERNS)

[응답 형식]
  {"score": 0.0~1.0, "category": "notify"|"silent", "reason": "한국어",
   "summary": "한국어 3줄 요약", "user_overrides": {"U12345": "silent"}}
"""
import json
import time
from typing import Optional
import httpx
from anthropic import AnthropicBedrock
from app.config import Config
from app.models import GmailEvent, AnalysisResult, ImportanceCategory, AnalysisSource
from app.utils.logger import get_logger
from app.utils.text_utils import strip_quoted_reply

logger = get_logger("llm_service")

ANTHROPIC_VERSION = "bedrock-2023-05-31"


class _TokenWatcherError(Exception):
    """Token Watcher 호출 실패 — 폴백 가능 여부를 can_fallback 속성으로 전달."""
    def __init__(self, message: str, can_fallback: bool = True):
        super().__init__(message)
        self.can_fallback = can_fallback


class LLMService:
    TW_FAIL_THRESHOLD = 3
    TW_CIRCUIT_TIMEOUT = 30

    def __init__(self):
        self.model_id = Config.BEDROCK_MODEL_ID
        self.client = self._init_client()
        self.tw_client = self._init_tw_client()
        self.tw_model_id = self._extract_model_id()
        # 서킷브레이커 상태
        self._tw_fail_count = 0
        self._tw_circuit_open_until = 0.0

    def _init_client(self):
        if not (Config.AWS_ACCESS_KEY_ID and Config.AWS_SECRET_ACCESS_KEY):
            return None
        try:
            return AnthropicBedrock(aws_access_key=Config.AWS_ACCESS_KEY_ID, aws_secret_key=Config.AWS_SECRET_ACCESS_KEY, aws_region=Config.AWS_REGION)
        except Exception:
            return None

    def _init_tw_client(self) -> Optional[httpx.Client]:
        if not (Config.TOKEN_WATCHER_URL and Config.TOKEN_WATCHER_KEY):
            return None
        return httpx.Client(timeout=30.0)

    def _extract_model_id(self) -> str:
        mid = self.model_id
        if mid.startswith("arn:"):
            return mid.rsplit("/", 1)[-1]
        return mid

    # ─── 서킷브레이커 ───────────────────────────────────────

    def _should_use_tw(self) -> bool:
        if not self.tw_client:
            return False
        if self._tw_fail_count >= self.TW_FAIL_THRESHOLD:
            if time.time() < self._tw_circuit_open_until:
                logger.info("[CIRCUIT] Token Watcher circuit open, using Bedrock direct")
                return False
            logger.info("[CIRCUIT] Token Watcher half-open, retrying")
        return True

    def _record_tw_failure(self):
        self._tw_fail_count += 1
        if self._tw_fail_count >= self.TW_FAIL_THRESHOLD:
            self._tw_circuit_open_until = time.time() + self.TW_CIRCUIT_TIMEOUT
            logger.warning(f"[CIRCUIT] Token Watcher circuit OPEN for {self.TW_CIRCUIT_TIMEOUT}s (failures={self._tw_fail_count})")

    def _record_tw_success(self):
        if self._tw_fail_count > 0:
            logger.info(f"[CIRCUIT] Token Watcher recovered (was {self._tw_fail_count} failures)")
        self._tw_fail_count = 0
        self._tw_circuit_open_until = 0.0

    # ─── 공개 API ────────────────────────────────────────────

    def analyze_email(self, event, user_preferences_map=None):
        sp = self._build_system_prompt()
        # 중요도 '판단'은 본문 없이(제목/발신자/스니펫) 수행 — 비용 절감.
        # 본문은 알림 대상(NOTIFY)으로 정해진 메일의 요약에만 사용한다(summarize_email).
        up = self._build_user_prompt(event, user_preferences_map, include_body=False)
        return self._call_llm(sp, up, max_tokens=512, use_cache=True)

    def summarize_email(self, event) -> tuple:
        """이메일 요약만 수행 (알림 대상 경로용 경량 호출).

        Returns: (summary: Optional[str], usage: Optional[dict])
        """
        sp = (
            "이메일을 한국어로 요약하세요.\n"
            "## 규칙\n"
            "- 정확히 3줄 이내로, 각 줄은 불릿 포인트(•)로 시작하고 줄바꿈(\\n)으로 구분\n"
            "- 제목·머리말 줄을 넣지 말 것 (예: '# 요약', '요약:' 같은 줄 금지)\n"
            "- 꾸밈 기호 금지: **굵게**, __, 앞머리 #, ~취소선~ 등 마크다운 장식을 쓰지 말 것 (순수 텍스트만)\n"
            "- 핵심 정보(누가·무엇을·왜)만 간결하게, 최소 10자 이상\n"
            "## 형식 예시\n"
            "• 첫번째 핵심 내용\n• 두번째 핵심 내용\n• 세번째 핵심 내용"
        )
        sn = event.raw_data.get('snippet', '') if event.raw_data else ''
        body = ''
        if event.raw_data and event.raw_data.get('body_text'):
            # 회신에 딸려온 이전 대화(인용)를 제거해 '이번 새 내용'만 요약 대상으로 삼는다.
            # (옛 대화가 요약에 혼입되는 문제 방지 + 입력 토큰 절감)
            cleaned = strip_quoted_reply(event.raw_data['body_text']) or ''
            body = cleaned[:Config.LLM_SUMMARY_BODY_MAX_CHARS]
        up = f"Subject: {event.subject or ''}\nSender: {event.sender}\n"
        if sn:
            up += f"Snippet: {sn}\n"
        if body:
            up += f"Body: {body}"

        try:
            # 3줄 한국어(+영문 용어 혼합) 요약이 중간에 잘리지 않도록 출력 상한을 넉넉히 둔다.
            # 실제 출력은 3줄뿐이라 과금은 출력분만 발생(상한만 확대, 비용 영향 미미).
            text, usage = self._call_llm_raw(sp, up, max_tokens=400, use_cache=False)
            return (text.strip() if text else None), usage
        except Exception as e:
            logger.warning(f"summarize_email failed: {e}")
        return None, None

    # ─── LLM 호출 오케스트레이션 ──────────────────────────────

    def _call_llm(self, sp, up, max_tokens=512, use_cache=True) -> AnalysisResult:
        """analyze_email용: TW v2 → Bedrock 폴백 → 안전 기본값."""
        # 1) Token Watcher v2 시도
        if self._should_use_tw():
            try:
                text, usage = self._call_token_watcher(sp, up, max_tokens, use_cache)
                self._record_tw_success()
                result = self._parse(text)
                result.llm_usage = usage
                return result
            except _TokenWatcherError as e:
                logger.warning(f"Token Watcher v2 fallback: {e}")
                self._record_tw_failure()
                if not e.can_fallback:
                    return AnalysisResult(score=0.5, category=ImportanceCategory.NOTIFY, reason="AI 분석 실패 - 안전을 위해 알림 전송", source=AnalysisSource.LLM)
            except Exception as e:
                logger.warning(f"Token Watcher v2 unexpected error: {e}")
                self._record_tw_failure()

        # 2) Bedrock 직접 호출 (폴백)
        return self._call_bedrock(sp, up, max_tokens, use_cache)

    def _call_llm_raw(self, sp, up, max_tokens=400, use_cache=False) -> tuple:
        """summarize_email용: TW v2 → Bedrock 폴백. (원시 텍스트, usage) 반환."""
        # 1) Token Watcher v2 시도
        if self._should_use_tw():
            try:
                text, usage = self._call_token_watcher(sp, up, max_tokens, use_cache)
                self._record_tw_success()
                return text, usage
            except _TokenWatcherError as e:
                logger.warning(f"Token Watcher v2 summarize fallback: {e}")
                self._record_tw_failure()
            except Exception as e:
                logger.warning(f"Token Watcher v2 summarize unexpected: {e}")
                self._record_tw_failure()

        # 2) Bedrock 직접 호출
        if not self.client:
            return None, None
        try:
            r = self.client.messages.create(
                model=self.model_id, max_tokens=max_tokens, temperature=0.0,
                system=[{"type": "text", "text": sp}],
                messages=[{"role": "user", "content": [{"type": "text", "text": up}]}]
            )
            text = "".join(b.text for b in r.content if b.type == "text").strip() or None
            return text, self._extract_usage(r)
        except Exception as e:
            logger.warning(f"Bedrock summarize failed: {e}")
        return None, None

    # ─── Token Watcher v2 ────────────────────────────────────

    def _call_token_watcher(self, sp, up, max_tokens, use_cache) -> tuple:
        """Token Watcher v2 호출. (text, usage_dict) 반환. 실패 시 _TokenWatcherError."""
        url = f"{Config.TOKEN_WATCHER_URL}/v1/chat/completions"
        payload = self._build_tw_payload(sp, up, max_tokens, use_cache)
        headers = {"Authorization": f"Bearer {Config.TOKEN_WATCHER_KEY}", "Content-Type": "application/json"}

        try:
            response = self.tw_client.post(url, headers=headers, json=payload)
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            raise _TokenWatcherError(str(e), can_fallback=True)

        # HTTP 에러
        if response.status_code >= 400:
            try:
                data = response.json()
            except Exception:
                raise _TokenWatcherError(f"HTTP {response.status_code}: {response.text[:200]}", can_fallback=response.status_code >= 500)

            if "error" in data:
                provider_status = data.get("provider_status", 0)
                err_msg = data["error"].get("message", "unknown")
                can_fallback = provider_status >= 500 or response.status_code >= 500
                raise _TokenWatcherError(f"TW error: {err_msg} (provider_status={provider_status})", can_fallback=can_fallback)

            raise _TokenWatcherError(f"HTTP {response.status_code}", can_fallback=response.status_code >= 500)

        # 성공 응답 파싱
        try:
            data = response.json()
        except Exception as e:
            raise _TokenWatcherError(f"JSON decode failed: {e}", can_fallback=True)

        text, usage = self._parse_tw_response(data)
        logger.info(f"Token Watcher v2 call OK (model={self.tw_model_id}, tokens={usage})")
        return text, usage

    def _build_tw_payload(self, sp, up, max_tokens, use_cache) -> dict:
        system_block = {"type": "text", "text": sp}
        if use_cache:
            system_block["cache_control"] = {"type": "ephemeral"}

        return {
            "provider": "bedrock",
            "model_id": self.tw_model_id,
            "stream": True,
            "pass_through_body": {
                "anthropic_version": ANTHROPIC_VERSION,
                "max_tokens": max_tokens,
                "system": [system_block],
                "messages": [
                    {"role": "user", "content": [{"type": "text", "text": up}]}
                ],
                "temperature": 0.0
            }
        }

    def _parse_tw_response(self, data: dict) -> tuple:
        """Token Watcher v2 응답에서 (text, usage_dict) 추출. 두 가지 형식 지원."""
        # 형식 1: Bedrock Messages API (content[].text)
        if "content" in data and isinstance(data["content"], list):
            text = "".join(
                c.get("text", "") for c in data["content"] if c.get("type") == "text"
            ).strip()
            usage = self._extract_tw_usage(data.get("usage"))
            return text, usage

        # 형식 2: v1 래핑 (output.message.content[].text) — 하위호환
        if "output" in data:
            content_list = data["output"]["message"]["content"]
            text = "".join(
                c.get("text", "") for c in content_list if isinstance(c, dict)
            ).strip()
            usage = self._extract_tw_usage(data.get("usage"))
            return text, usage

        raise _TokenWatcherError(f"Unknown TW response format: {list(data.keys())}", can_fallback=True)

    def _extract_tw_usage(self, usage) -> Optional[dict]:
        if not usage or not isinstance(usage, dict):
            return None
        return {
            "input_tokens": usage.get("input_tokens", usage.get("inputTokens", 0)),
            "output_tokens": usage.get("output_tokens", usage.get("outputTokens", 0)),
            "cache_write_tokens": usage.get("cache_creation_input_tokens", 0),
            "cache_read_tokens": usage.get("cache_read_input_tokens", 0),
            "model_id": self.tw_model_id,
        }

    # ─── Bedrock 직접 호출 (폴백) ─────────────────────────────

    def _call_bedrock(self, sp, up, max_tokens=512, use_cache=True):
        if not self.client:
            logger.error("Bedrock client not initialized")
            return AnalysisResult(score=0.0, category=ImportanceCategory.SILENT, reason="AI 연결 불가", source=AnalysisSource.LLM)
        try:
            system_block = {"type": "text", "text": sp}
            if use_cache:
                system_block["cache_control"] = {"type": "ephemeral"}
            response = self.client.messages.create(model=self.model_id, max_tokens=max_tokens, temperature=0.0, system=[system_block], messages=[{"role": "user", "content": [{"type": "text", "text": up}]}])
            content_text = "".join(b.text for b in response.content if b.type == "text").strip()
            usage = self._extract_usage(response)
            result = self._parse(content_text)
            result.llm_usage = usage
            return result
        except Exception as e:
            logger.error(f"Bedrock call failed: {e}")
            return AnalysisResult(score=0.5, category=ImportanceCategory.NOTIFY, reason="AI 분석 실패 - 안전을 위해 알림 전송", source=AnalysisSource.LLM)

    # ─── 공통 파서 ────────────────────────────────────────────

    def _parse(self, ct):
        s=ct.find('{'); e=ct.rfind('}')
        if s!=-1 and e!=-1: ct=ct[s:e+1]
        p=json.loads(ct)
        cat=ImportanceCategory.NOTIFY if p.get("category","silent").lower() in ["critical","important","normal","notify"] else ImportanceCategory.SILENT
        summary = p.get("summary")
        if summary is not None:
            summary = summary.strip() if isinstance(summary, str) else summary
            if not summary or len(summary) < 10:
                summary = None
        return AnalysisResult(score=float(p.get("score",0.0)),category=cat,reason=p.get("reason",""),summary=summary,source=AnalysisSource.LLM,raw_data={"user_overrides":p.get("user_overrides",{})})

    def _extract_usage(self, r):
        u=getattr(r,"usage",None)
        if not u: return None
        return {"input_tokens":getattr(u,"input_tokens",0),"output_tokens":getattr(u,"output_tokens",0),"cache_write_tokens":getattr(u,"cache_creation_input_tokens",0),"cache_read_tokens":getattr(u,"cache_read_input_tokens",0),"model_id":self.model_id}

    @staticmethod
    def _merge_usage(a: Optional[dict], b: Optional[dict]) -> Optional[dict]:
        """두 LLM usage dict를 합산한다(판단 호출 + 요약 호출 비용 합산용)."""
        if not a:
            return dict(b) if b else None
        if not b:
            return dict(a)
        merged = dict(a)
        for k in ("input_tokens", "output_tokens", "cache_write_tokens", "cache_read_tokens"):
            merged[k] = (a.get(k, 0) or 0) + (b.get(k, 0) or 0)
        return merged

    def _build_system_prompt(self):
        return (
            "You are an expert email triage AI. Return ONLY valid JSON.\n\n"
            "## 응답 형식 (JSON)\n"
            '{"score": float(0.0~1.0), "category": "notify"|"silent", '
            '"reason": "한국어로 분류 사유 작성", '
            '"summary": "한국어로 핵심 요약 작성", '
            '"user_overrides": {}}\n\n'
            "## 분류 기준\n"
            "- NOTIFY: 업무 관련, 법률/재무, 사람 간 커뮤니케이션\n"
            "- SILENT: 뉴스레터, 자동화 알림, 마케팅\n\n"
            "## 요약(summary) 작성 규칙\n"
            "- 반드시 한국어로 작성할 것\n"
            "- 반드시 불릿 포인트(•) 형식으로 각 항목을 줄바꿈하여 3줄로 작성할 것\n"
            "- 형식: \"• 첫번째 핵심\\n• 두번째 핵심\\n• 세번째 핵심\"\n"
            "- 단순 번역이 아닌, 메일의 핵심 정보를 추출하여 구체적이고 정보가 담긴 요약을 작성할 것\n"
            "- 요약은 최소 10자 이상이어야 함\n"
            "- 누가, 무엇을, 왜 보냈는지 핵심만 간결하게 포함할 것\n\n"
            "## 요약 예시\n"
            '"• 프로젝트 일정이 2주 연기됨\\n• 다음 주 월요일까지 수정된 계획서 제출 요청\\n• 팀 전체 일정 재조정 필요"\n'
            '"• 서버 장애 발생으로 긴급 대응 필요\\n• 현재 복구 작업 진행 중\\n• 영향 범위 확인 후 공유 예정"\n'
            '"• 월간 매출 보고서 검토 요청\\n• 전월 대비 15% 증가 확인 필요\\n• 금주 금요일까지 피드백 요청"'
        )

    def _build_user_prompt(self, event, upm=None, include_body=True):
        sn = event.raw_data.get('snippet','N/A') if event.raw_data else 'N/A'
        p = f"Subject: {event.subject or ''}\nSender: {event.sender}\nRecipients: {', '.join(event.recipients)}\nOwner: {event.owner}\nEventType: {event.event_type}\nSnippet: {sn}"
        # 본문은 본문이 꼭 필요한 경우(요약 등, include_body=True)에만 포함.
        # 중요도 판단(analyze_email)은 include_body=False로 호출하여 비용을 절감한다.
        if include_body and event.raw_data and event.raw_data.get('body_text'):
            body = event.raw_data['body_text']
            max_chars = Config.LLM_SUMMARY_BODY_MAX_CHARS
            if len(body) > max_chars:
                body = body[:max_chars]
            p += f"\nBody: {body}"
        if upm:
            p += "\n\n### MUTED PATTERNS\n"
            for uid, prefs in upm.items():
                for pr in prefs:
                    p += f"- User:{uid} Sender:{pr.get('sender')} Type:{pr.get('subject_pattern','N/A')}\n"
        return p
