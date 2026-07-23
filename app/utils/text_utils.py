"""text_utils.py - 이메일 본문 텍스트 유틸.

회신 메일에 누적되는 이전 대화 인용(quoted reply)을 제거하여 '이번에
새로 작성된 내용'만 남긴다. AI 요약이 답장에 딸려온 옛 대화를 새 내용으로
오인해 요약에 섞는 문제(운영 관찰: 긴 스레드 회신의 인용이 요약에 혼입)를
방지한다.

[ReDoS 방지 — 이중 방어]
  1) 탐지 범위를 본문 앞부분(_SCAN_LIMIT)으로 제한한다. 회신 경계는 사실상
     본문 상단에 있고 요약도 앞 LLM_SUMMARY_BODY_MAX_CHARS만 쓰므로, 전체
     (수백 KB 가능)를 스캔할 이유가 없다. 대용량/악성 본문에서의 백트래킹
     폭주(CPU-DoS)를 원천 차단한다.
  2) 패턴은 개행을 넘지 않고(\\s 대신 [ \\t]) 유계 수량자만 사용해, 창 안에서도
     2차 백트래킹이 발생하지 않도록 한다.
"""
import re
from typing import Optional

from app.config import Config

# 경계 탐지 범위 상한. 최종 출력은 LLM_SUMMARY_BODY_MAX_CHARS로 잘리므로 그 뒤
# (+여유 2000)의 마커는 결과에 영향이 없다. MAX와 커플링해 향후 상향에도 안전.
_SCAN_LIMIT = Config.LLM_SUMMARY_BODY_MAX_CHARS + 2000

# --- 강한 마커: 이메일 헤더/구분선 형태라 오탐 위험 사실상 0 → 남는 앞부분이 짧아도 절단 ---
_STRONG_PATTERNS = [
    r'-{2,80}[ \t]*(?:Original Message|원본 메시지)[ \t]*-{2,80}',                    # -----Original Message-----
    r'^[ \t]*From:[ \t].+\r?\n[ \t]*(?:Sent|Date|To|Cc|보낸 날짜|받는 사람)[ \t]*:',   # Outlook 헤더 블록(영/한)
    r'^[ \t]*보낸 사람[ \t]*:[ \t].+\r?\n[ \t]*(?:보낸 날짜|받는 사람|날짜|제목)[ \t]*:',  # 한글 Outlook 블록
    r'^[ \t]*On[ \t].{0,200}?\bwrote:[ \t]*$',                                        # Gmail 영문 'On ... wrote:'
    r'^[ \t]*(?:19|20)\d{2}[.\-/년].{0,80}?(?:<[^>\n]+>|님이)[ \t]*작성[ \t]*:',        # Gmail 한글(이메일/님이 + 콜론 필수)
]
# --- 약한 마커: 정상 본문에도 나타날 수 있어 → 남는 앞부분이 충분할 때만 절단 ---
_WEAK_PATTERNS = [
    r'^[ \t]*_{10,200}[ \t]*$',   # Outlook 밑줄 구분선(단독 라인)
    r'^[ \t]*>',                  # '>' 인용 라인
]

_STRONG_RE = re.compile('|'.join(f'(?:{p})' for p in _STRONG_PATTERNS), re.MULTILINE)
_WEAK_RE = re.compile('|'.join(f'(?:{p})' for p in _WEAK_PATTERNS), re.MULTILINE)

# 절단 후 남는 '새 내용'이 이 길이 미만이면, 약한 마커에 한해 과다절단으로 보고 원문을 유지.
_MIN_KEEP_CHARS = 15


def strip_quoted_reply(text: Optional[str]) -> Optional[str]:
    """회신 인용(이전 대화)을 제거하고 새로 작성된 앞부분만 반환.

    - 강한 마커(이메일 헤더/구분선): 위치와 무관하게 그 앞을 새 내용으로 채택.
    - 약한 마커('>' 인용, 밑줄선): 남는 앞부분이 _MIN_KEEP_CHARS 이상일 때만
      절단(정상 본문 오절단 방지).
    - 마커가 없거나, 절단하면 남는 게 없으면 원문 그대로 반환.
    - 탐지는 앞부분(_SCAN_LIMIT)으로 제한해 ReDoS를 방지한다.
    """
    if not text:
        return text
    limit = min(len(text), _SCAN_LIMIT)
    cut = None
    ms = _STRONG_RE.search(text, 0, limit)
    if ms:
        cut = ms.start()
    mw = _WEAK_RE.search(text, 0, limit)
    if mw and len(text[:mw.start()].strip()) >= _MIN_KEEP_CHARS:
        if cut is None or mw.start() < cut:
            cut = mw.start()
    if cut is None:
        return text
    head = text[:cut].strip()
    return head if head else text
