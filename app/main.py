"""
main.py - Flask 애플리케이션 엔트리포인트

[API 엔드포인트]
  POST /run-batch           - 배치 실행 (Cloud Scheduler가 5분마다 호출)
  POST /trigger-notification - 관리자 수동 알림 전송 + 학습
  POST /block-notification   - 관리자 수동 차단 + 학습
  POST /slack/interactive    - Slack 버튼 클릭 처리 (알림 차단/해제/읽음 처리)

[배치 처리 흐름] (/run-batch)
  1. 시스템 상태 체크 (일시중지/한도초과 시 스킵)
  2. 등록된 모든 사용자의 Gmail 미읽은 메일 조회
  3. 각 메일을 병렬로 처리 (process_single_event)
     a. 라우팅 대상자 조회
     b. 중복 체크 (이미 처리된 메일이면 LLM 스킵)
     c. AI 분류 (Classifier) → 규칙 기반 차단 체크
     d. Slack 알림 전송
     e. Firestore에 스냅샷 저장 + 일일 사용량 업데이트
"""
import sys
import json
import argparse
import hmac
import hashlib
import threading
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from app.config import Config
from app.utils.logger import setup_logging, get_logger
from app.utils.state_store import create_state_store
from app.services.gmail_service import GmailService
from app.services.slack_service import SlackService
from app.models import ProcessedResult, ImportanceCategory, GmailEvent, AnalysisResult, AnalysisSource, NotificationTarget
from app.core.classifier import Classifier
from app.core.router import Router

# ── 초기화 ──────────────────────────────────────────
load_dotenv()
setup_logging()
logger = get_logger("main")

app = Flask(__name__)

# Slack 인터랙션 및 관리자 API에 CORS 허용
CORS(app, resources={
    r"/slack/*": {"origins": "*"},
    r"/trigger-notification": {"origins": "*"},
    r"/block-notification": {"origins": "*"}
})

# ── 서비스 인스턴스 ──────────────────────────────────
state_store = create_state_store()   # 중복 알림 방지 (File 또는 Firestore)
gmail_service = None                 # Gmail API 클라이언트 (lazy init)
classifier = Classifier()           # 이메일 중요도 분류기 (규칙 + AI)
router = Router()                   # 이메일 → Slack 대상 라우팅
slack_service = SlackService()       # Slack Bot 메시지 전송

# --dry-run 옵션: 실제 Slack 전송 없이 테스트
parser = argparse.ArgumentParser()
parser.add_argument("--dry-run", action="store_true", help="Run without sending Slack notifications")
args, unknown = parser.parse_known_args()
DRY_RUN = args.dry_run

if DRY_RUN:
    logger.info("⚠️ RUNNING IN DRY-RUN MODE. No notifications will be sent.")

def get_gmail_service():
    """Gmail API 클라이언트를 lazy 초기화하여 반환 (첫 호출 시에만 생성)"""
    global gmail_service
    if gmail_service is None:
        gmail_service = GmailService()
    return gmail_service

def _check_internal_auth():
    """내부 API 엔드포인트 인증 체크.
    INTERNAL_API_KEY 설정 시 Authorization: Bearer {key} 헤더 필수.
    미설정 시 스킵 (로컬 개발 환경 호환).
    """
    api_key = Config.INTERNAL_API_KEY
    if not api_key:
        return None
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer ') or auth_header[7:] != api_key:
        logger.warning(f"Unauthorized internal API call from {request.remote_addr}")
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    return None

@app.route('/run-batch', methods=['POST'])
def run_batch():
    auth_err = _check_internal_auth()
    if auth_err:
        return auth_err
    try:
        logger.info("Starting batch processing...")

        # ✅ 시스템 상태 체크 (일시 중지 또는 한도 초과 시 즉시 리턴)
        from app.services.settings_store import SettingsStore
        settings = SettingsStore()
        enabled, reason = settings.is_system_enabled()
        
        if not enabled:
            logger.warning(f"Batch skipped: {reason}")
            return jsonify({
                "status": "skipped",
                "reason": reason,
                "processed": 0,
                "sent": 0,
                "ignored": 0
            }), 200
        
        Config.validate()
        from app.services.routing_store import RoutingStore
        routing_store = RoutingStore()
        user_emails = routing_store.get_all_monitored_emails()
        
        events = get_gmail_service().fetch_unread_emails(user_emails)
        results = []
        
        from concurrent.futures import ThreadPoolExecutor, as_completed
        # LLM 호출 병렬화를 위해 스레드 사용 (10~15개 적절)
        max_workers = min(len(events), 15) if events else 1
        
        if events:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_event = {executor.submit(process_single_event, event): event for event in events}
                for future in as_completed(future_to_event):
                    event = future_to_event[future]
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        logger.error(f"Error processing {event.message_id}: {e}")
        
        sent_count = sum(1 for r in results if r.notification_sent)
        ignored_count = sum(1 for r in results if r.analysis.category == ImportanceCategory.SILENT)
        
        # ✅ 배치 실행 정보 업데이트
        settings.update_last_batch_info(len(results))

        # ✅ 사용량 기반 알림 — daily_usage를 1회만 읽어 두 알림(한도 근접 + 급증)이 공용
        usage = {}
        try:
            usage = settings.get_daily_usage()
        except Exception as e:
            logger.error(f"get_daily_usage failed: {e}")

        # (1) 비용 한도 근접 알림 (한도 대비 임계값 초과 시 담당자에게 DM)
        try:
            if usage and not usage.get("cost_alert_sent", False):
                alert_cfg = settings.get_cost_alert_settings()  # TTL 캐시 경유
                status = settings.get_system_status()
                limit_cost = status.get("daily_limit_cost_usd", 5.0)
                current_cost = usage.get("cost_usd", 0.0)
                if limit_cost > 0 and (current_cost / limit_cost) >= alert_cfg["threshold_percent"]:
                    sent = slack_service.send_cost_alert_dm(
                        recipient_id=alert_cfg["slack_channel"],
                        current_cost_usd=current_cost,
                        limit_cost_usd=limit_cost,
                        threshold_percent=alert_cfg["threshold_percent"],
                        date_str=usage.get("date", ""),
                    )
                    if sent:
                        settings.mark_cost_alert_sent_today()
        except Exception as e:
            logger.error(f"Cost alert check failed: {e}")

        # (2) 급증 감지 알림 — 고정 한도와 무관하게 최근 평균 대비 급증 시 즉시 통보 (재발 방지 핵심)
        try:
            if usage and not usage.get("spike_alert_sent", False):
                is_spike, spike_detail = settings.check_usage_spike(today_usage=usage)
                if is_spike:
                    logger.warning(f"[SPIKE] Usage spike detected: {spike_detail}")
                    alert_cfg = settings.get_cost_alert_settings()
                    sent = slack_service.send_usage_spike_alert_dm(
                        recipient_id=alert_cfg["slack_channel"],
                        detail=spike_detail,
                    )
                    if sent:
                        settings.mark_spike_alert_sent_today()
        except Exception as e:
            logger.error(f"Usage spike check failed: {e}")

        return jsonify({
            "status": "success",
            "processed": len(results),
            "sent": sent_count,
            "ignored": ignored_count
        }), 200
    except Exception as e:
        logger.error(f"Batch failed: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/trigger-notification', methods=['POST'])
def trigger_notification():
    """알림 수동 전송 및 '앞으로 알림 받기' 학습"""
    auth_err = _check_internal_auth()
    if auth_err:
        return auth_err
    try:
        data = request.json
        email_id = data.get('email_id')
        target_ids = data.get('target_ids', [])
        learn = data.get('learn', True)

        from app.services.learning_store import get_email_event, delete_user_silent_preference
        event_dict = get_email_event(email_id)
        if not event_dict: return jsonify({"status": "error", "message": "Event not found"}), 404

        # Reconstruct Event
        event = GmailEvent(
            timestamp=event_dict.get('timestamp'),
            message_id=event_dict.get('email_id'),
            subject=event_dict.get('subject'),
            sender=event_dict.get('from_email'),
            recipients=[event_dict.get('to_email')],
            owner=event_dict.get('to_email'),
            event_type='MANUAL_TRIGGER'
        )
        # Firestore에 저장된 summary와 reason을 가져와서 사용
        saved_summary = event_dict.get('summary')
        saved_reason = event_dict.get('reason', '관리자 수동 전송')
        analysis = AnalysisResult(
            score=1.0, 
            category=ImportanceCategory.NOTIFY, 
            reason=saved_reason, 
            summary=saved_summary,
            source=AnalysisSource.RULE
        )

        # Real-time target lookup if missing
        if not target_ids:
            targets = router.get_targets(event)
            target_ids = [t.target_id for t in targets]
        
        if not target_ids: return jsonify({"status": "error", "message": "No targets available"}), 400
        targets = [NotificationTarget(target_id=tid, target_type="user" if tid.startswith('U') else "channel") for tid in target_ids]

        # Send
        if slack_service.send_notification(targets, event, analysis):
            # 1. 학습: 기존에 차단(Silent) 되어 있었다면 해당 설정을 삭제함
            if learn:
                for tid in target_ids:
                    if tid.startswith('U'):
                        delete_user_silent_preference(user_id=tid, sender=event.sender, subject=event.subject)
            
            # 2. DB 업데이트 (reason 포함)
            from app.services.learning_store import _get_firestore_client, COLLECTION_EMAIL_EVENTS
            db = _get_firestore_client()
            if db:
                db.collection(COLLECTION_EMAIL_EVENTS).document(email_id).update({
                    "final_category": "notify",
                    "reason": "관리자가 수동으로 알림 전송 및 학습 처리함",
                    "manually_triggered": True,
                    "triggered_at": datetime.utcnow()
                })
            
            for target in targets:
                state_store.mark_processed(email_id, target.target_id, sender=event.sender, subject=event.subject)
            return jsonify({"status": "success"}), 200
        return jsonify({"status": "error", "message": "Slack send failed"}), 500
    except Exception as e:
        logger.error(f"Manual trigger failed: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/block-notification', methods=['POST'])
def block_notification():
    """알림 수동 차단 및 '앞으로 무시' 학습"""
    auth_err = _check_internal_auth()
    if auth_err:
        return auth_err
    try:
        data = request.json
        email_id = data.get('email_id')
        
        from app.services.learning_store import get_email_event, save_user_silent_preference, extract_email_type_pattern
        event_dict = get_email_event(email_id)
        if not event_dict: return jsonify({"status": "error", "message": "Event not found"}), 404

        sender = event_dict.get('from_email')
        subject = event_dict.get('subject')  # 제목도 가져오기
        target_ids = event_dict.get('slack_targets', [])

        # 1. 학습: 발신자 + 유형 패턴을 차단 리스트에 추가
        if sender and target_ids:
            type_pattern = extract_email_type_pattern(subject)
            for tid in target_ids:
                if tid.startswith('U'):
                    save_user_silent_preference(user_id=tid, sender=sender, subject=subject)
        
        # 2. DB 업데이트 (reason 포함)
        from app.services.learning_store import _get_firestore_client, COLLECTION_EMAIL_EVENTS
        db = _get_firestore_client()
        if db:
            type_pattern = extract_email_type_pattern(subject)
            db.collection(COLLECTION_EMAIL_EVENTS).document(email_id).update({
                "final_category": "silent",
                "reason": f"관리자가 수동으로 차단 처리함 (발신자: {sender}, 유형: {type_pattern})",
                "manually_blocked": True,
                "blocked_at": datetime.utcnow()
            })
        
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error(f"Manual block failed: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

def process_single_event(event) -> ProcessedResult:
    """
    개별 이메일 처리 파이프라인 (병렬 실행됨)
    
    [처리 순서]
    1. 라우팅 대상자 조회 (Router)
    2. 중복 체크: 이미 처리된 메일이면 캐시된 결과 재사용 (LLM 비용 절감)
    3. AI 분류 (Classifier): 규칙 기반 필터 → LLM 분석 → 임계값 적용
    4. 규칙 기반 차단: 사용자가 Slack에서 차단한 발신자/유형 체크
    5. Firestore에 이메일 스냅샷 저장 + 일일 사용량 업데이트
    6. 중복 알림 방지 후 Slack 전송
    """
    targets = router.get_targets(event)
    if not targets:
        return ProcessedResult(event=event, analysis=AnalysisResult(score=0.0, category=ImportanceCategory.SILENT, reason="알림 대상자 없음", source=AnalysisSource.RULE), targets=[], notification_sent=False)

    # ✅ 중복 체크: LLM 호출 전에 이미 처리된 메일인지 확인 (비용 절감)
    from app.services.learning_store import get_user_silent_preferences, get_email_event
    try:
        existing_event = get_email_event(event.message_id)
    except Exception as e:
        # Firestore 오류 시 LLM 호출 스킵 (비용 폭증 방지)
        logger.error(f"[{event.message_id[:30]}] Firestore unavailable, skipping LLM: {e}")
        return ProcessedResult(event=event, analysis=AnalysisResult(score=0.0, category=ImportanceCategory.SILENT, reason=f"Firestore 오류로 처리 보류", source=AnalysisSource.RULE), targets=targets, notification_sent=False)

    if existing_event:
        # 이미 처리된 메일 → 기존 분석 결과 재사용, LLM 호출 스킵
        logger.info(f"[{event.message_id[:30]}] Already processed, reusing cached result (LLM skipped)")
        try:
            cached_category = ImportanceCategory(existing_event.get('final_category', 'silent'))
        except ValueError:
            cached_category = ImportanceCategory.SILENT
        
        analysis = AnalysisResult(
            score=existing_event.get('llm_score_raw', 0.0) or 0.0,
            category=cached_category,
            reason=existing_event.get('reason', '이전 분석 결과 재사용'),
            summary=existing_event.get('summary'),
            source=AnalysisSource.RULE  # 캐시된 결과임을 표시
        )
        # user_overrides는 기존 결과에서 가져올 수 없으므로 빈 값 사용
        llm_usage = None
    else:
        # 신규 메일 → LLM 호출
        user_preferences_map = {}
        for target in targets:
            if target.target_type == "user":
                prefs = get_user_silent_preferences(target.target_id)
                if prefs: user_preferences_map[target.target_id] = prefs

        # 배치 중 실시간 한도 체크 (병렬 스레드에서 한도 돌파 방지)
        from app.services.settings_store import SettingsStore
        mid_batch_settings = SettingsStore()
        enabled, reason = mid_batch_settings.is_system_enabled()
        if not enabled:
            logger.info(f"[BATCH] Daily limit reached mid-batch, skipping {event.subject[:50] if event.subject else ''}")
            return ProcessedResult(event=event, analysis=AnalysisResult(score=0.0, category=ImportanceCategory.SILENT, reason=f"한도 초과 스킵: {reason}", source=AnalysisSource.RULE), targets=targets, notification_sent=False)

        analysis = classifier.classify(event, user_preferences_map)
        # LLM 사용량 정보 (결과 객체에 담겨 옴 — 병렬 처리 시 스레드 안전)
        llm_usage = analysis.llm_usage
    final_targets = []
    user_overrides = analysis.raw_data.get("user_overrides", {}) if analysis.raw_data else {}
    
    # ✅ 규칙 기반 차단: LLM 결과와 무관하게 사용자 차단 목록 직접 체크
    from app.services.learning_store import should_silence_for_user
    
    for target in targets:
        # 1. 규칙 기반 차단 (최우선)
        if target.target_type == "user" and should_silence_for_user(target.target_id, event.sender, event.subject):
            logger.info(f"[{event.message_id[:30]}] Target {target.target_id} silenced by rule-based preference")
            continue
        
        # 2. LLM user_overrides (보조)
        if target.target_id in user_overrides:
            if user_overrides[target.target_id] == "silent": continue
            elif user_overrides[target.target_id] == "notify":
                final_targets.append(target)
                continue
        
        # 3. 기본: 분석 결과에 따라
        if analysis.category == ImportanceCategory.NOTIFY:
            final_targets.append(target)

    # Always save snapshot for new events (이미 캐시된 결과를 사용한 경우는 제외)
    is_new = not state_store.is_processed(event.message_id, "")
    # existing_event가 있으면 이미 저장된 것이므로 다시 저장하지 않음
    should_save = (is_new or analysis.category == ImportanceCategory.NOTIFY) and not existing_event
    logger.info(f"[{event.message_id[:30]}] Snapshot check: is_new={is_new}, category={analysis.category.value}, cached={bool(existing_event)}, should_save={should_save}")
    
    if should_save:
        try:
            from app.services.learning_store import save_email_event_snapshot
            # 토큰 사용량 추출
            input_tokens = llm_usage.get("input_tokens") if llm_usage else None
            output_tokens = llm_usage.get("output_tokens") if llm_usage else None
            cache_read_tokens = llm_usage.get("cache_read_tokens") if llm_usage else None
            cache_write_tokens = llm_usage.get("cache_write_tokens") if llm_usage else None
            
            result = save_email_event_snapshot(
                email_id=event.message_id, subject=event.subject,
                from_email=event.sender, from_domain=event.sender.split('@')[-1] if '@' in event.sender else "",
                to_email=event.owner, timestamp=event.timestamp,
                rule_decision=analysis.source.value, llm_score_raw=analysis.score,
                llm_category_raw=analysis.category.value, llm_score_adjusted=analysis.score,
                prior_used="none", prior_value=None, alpha_used=None,
                final_category=analysis.category.value,
                slack_targets=[t.target_id for t in final_targets] if final_targets else [t.target_id for t in targets],
                reason=analysis.reason,
                summary=analysis.summary,  # AI 핵심 요약 추가
                thread_id=None, canonical_message_id=event.message_id,
                # 토큰 사용량 (비용 추적용)
                llm_input_tokens=input_tokens,
                llm_output_tokens=output_tokens,
                llm_cache_read_tokens=cache_read_tokens,
                llm_cache_write_tokens=cache_write_tokens,
            )
            logger.info(f"[{event.message_id[:30]}] Snapshot save result: {result}, tokens: in={input_tokens}, out={output_tokens}")
            
            # ✅ 일일 사용량 업데이트 (LLM 호출이 있었던 경우만)
            if llm_usage and (input_tokens or output_tokens):
                from app.services.settings_store import SettingsStore
                settings = SettingsStore()
                # 비용 계산 (Claude Haiku 4.5 기준). 캐시 토큰도 반영해 과소측정 방지
                # (Anthropic 표준 배수: cache write ≈ 1.25x, cache read ≈ 0.1x of input rate).
                cost_usd = (
                    (input_tokens or 0) * 0.80
                    + (output_tokens or 0) * 4.00
                    + (cache_write_tokens or 0) * 1.00
                    + (cache_read_tokens or 0) * 0.08
                ) / 1_000_000
                settings.increment_daily_usage(
                    calls=1,
                    cost_usd=cost_usd,
                    input_tokens=input_tokens or 0,
                    output_tokens=output_tokens or 0
                )
        except Exception as e:
            logger.warning(f"Snapshot error for {event.message_id[:30]}: {e}")

    if not final_targets: return ProcessedResult(event=event, analysis=analysis, targets=[], notification_sent=False)
    
    new_targets = [t for t in final_targets if not state_store.is_processed(event.message_id, t.target_id) and not state_store.is_duplicate_by_content(event.sender, event.subject, t.target_id, window_minutes=10)]
    
    if not new_targets: return ProcessedResult(event=event, analysis=analysis, targets=final_targets, notification_sent=False)
    
    if DRY_RUN:
        logger.info(f"[DRY-RUN] Would send notification to {[t.target_id for t in new_targets]} for {event.subject}")
        for t in new_targets:
            state_store.mark_processed(event.message_id, t.target_id, sender=event.sender, subject=event.subject)
        return ProcessedResult(event=event, analysis=analysis, targets=new_targets, notification_sent=True)

    if slack_service.send_notification(new_targets, event, analysis):
        for t in new_targets:
            state_store.mark_processed(event.message_id, t.target_id, sender=event.sender, subject=event.subject)
        return ProcessedResult(event=event, analysis=analysis, targets=new_targets, notification_sent=True)
    return ProcessedResult(event=event, analysis=analysis, targets=new_targets, notification_sent=False)

def _send_slack_response(response_url: str, data: dict):
    """response_url로 비동기 응답 전송"""
    try:
        resp = requests.post(
            response_url,
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        logger.info(f"[SLACK] response_url POST result: {resp.status_code}")
    except Exception as e:
        logger.error(f"[SLACK] response_url POST failed: {e}")

@app.route('/slack/interactive', methods=['POST', 'OPTIONS'])
def slack_interactive():
    """Slack interactive components (버튼 클릭 등) 처리 엔드포인트
    
    Cold Start 타임아웃 방지를 위해 response_url로 비동기 응답 전송
    """
    if request.method == 'OPTIONS':
        return '', 204

    # Slack 서명 검증 (미설정 시 요청 거부)
    slack_signing_secret = Config.SLACK_SIGNING_SECRET
    if not slack_signing_secret:
        logger.error("[SECURITY] SLACK_SIGNING_SECRET not set. Rejecting Slack request.")
        return '', 403

    timestamp = request.headers.get('X-Slack-Request-Timestamp', '')
    slack_signature = request.headers.get('X-Slack-Signature', '')
    if not timestamp or not slack_signature:
        return '', 403
    # 리플레이 공격 방지: 5분 이내 요청만 허용
    import time
    if abs(time.time() - float(timestamp)) > 300:
        return '', 403
    sig_basestring = f"v0:{timestamp}:{request.get_data(as_text=True)}"
    computed = 'v0=' + hmac.new(
        slack_signing_secret.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(computed, slack_signature):
        return '', 403

    try:
        payload_raw = request.form.get('payload')
        if not payload_raw: 
            return '', 400
        
        payload = json.loads(payload_raw)
        response_url = payload.get('response_url')
        logger.info(f"[SLACK] Received: type={payload.get('type')}, response_url exists={bool(response_url)}")
        
        if payload.get('type') == 'block_actions':
            action = payload['actions'][0]
            action_id = action.get('action_id')
            user_id = payload.get('user', {}).get('id')
            logger.info(f"[SLACK] Action: {action_id} by user {user_id}")
            
            if action_id == 'silent_forever':
                v = json.loads(action['value'])
                sender = v.get('sender', 'Unknown')
                subject = v.get('subject', '(제목 없음)')
                
                # 원래 메시지 블록 가져오기
                original_message = payload.get('message', {})
                original_blocks = original_message.get('blocks', [])
                
                # 백그라운드에서 모든 처리 수행
                def process_silent_forever(uid, snd, subj, resp_url, orig_blocks):
                    try:
                        # 1. 학습 저장 (subject 포함하여 유형 패턴 추출)
                        from app.services.learning_store import save_user_silent_preference, extract_email_type_pattern
                        save_result = save_user_silent_preference(user_id=uid, sender=snd, subject=subj)
                        type_pattern = extract_email_type_pattern(subj)

                        if not save_result:
                            logger.error(f"[SLACK] Failed to save silent preference for {uid}, {snd}, type: {type_pattern}")
                            # 저장 실패 시 사용자에게 에러 알림
                            error_data = {
                                "replace_original": False,
                                "text": f"⚠️ 알림 차단 저장에 실패했습니다. 잠시 후 다시 시도해주세요. (발신자: {snd})"
                            }
                            _send_slack_response(resp_url, error_data)
                            return

                        logger.info(f"[SLACK] Saved silent preference for {uid}, {snd}, type: {type_pattern}")
                        
                        # 2. 원래 메시지 블록 유지하면서 버튼만 교체
                        new_blocks = []
                        for block in orig_blocks:
                            # 기존 context 블록 중 알림 상태 관련 메시지는 제거 (중복 방지)
                            if block.get('type') == 'context':
                                elements = block.get('elements', [])
                                if elements and ('알림 차단' in str(elements) or '알림 차단 해제됨' in str(elements)):
                                    continue
                            
                            # 기존 actions 블록을 찾아 내용물만 수정
                            if block.get('type') == 'actions':
                                new_elements = []
                                for element in block.get('elements', []):
                                    # '알림 차단' 버튼만 '다시 알림 받기'로 교체
                                    if element.get('action_id') == 'silent_forever':
                                        new_elements.append({
                                            "type": "button",
                                            "text": {"type": "plain_text", "text": "다시 알림 받기"},
                                            "value": json.dumps({"sender": snd, "subject": subj}),
                                            "action_id": "undo_silent"
                                        })
                                    else:
                                        # Gmail 열기, 읽음 처리 버튼은 그대로 유지
                                        new_elements.append(element)
                                block['elements'] = new_elements
                            
                            new_blocks.append(block)
                        
                        # 차단 완료 상태 메시지 추가 (actions 블록 바로 앞에 삽입)
                        final_blocks = []
                        for block in new_blocks:
                            if block.get('type') == 'actions':
                                final_blocks.append({
                                    "type": "context",
                                    "elements": [
                                        {
                                            "type": "mrkdwn",
                                            "text": f"🔕 *알림 차단됨* — `{type_pattern}` 유형의 메일 알림을 차단했습니다."
                                        }
                                    ]
                                })
                            final_blocks.append(block)
                        
                        response_data = {
                            "replace_original": True,
                            "blocks": final_blocks
                        }
                        _send_slack_response(resp_url, response_data)
                    except Exception as e:
                        logger.error(f"[SLACK] process_silent_forever error: {e}", exc_info=True)
                        if resp_url:
                            _send_slack_response(resp_url, {"text": "처리 중 오류가 발생했습니다. 다시 시도해 주세요."})

                if response_url:
                    thread = threading.Thread(target=process_silent_forever, args=(user_id, sender, subject, response_url, original_blocks))
                    thread.start()
                    # 즉시 빈 응답 (Slack 타임아웃 방지)
                    return '', 200
                else:
                    # response_url이 없으면 동기 응답 (fallback)
                    from app.services.learning_store import save_user_silent_preference
                    save_user_silent_preference(user_id=user_id, sender=sender, subject=subject)
                    return jsonify({
                        "replace_original": True,
                        "text": f"🔕 `{sender}` 발신자의 알림을 차단했습니다."
                    })

            elif action_id == 'undo_silent':
                v = json.loads(action['value'])
                sender = v.get('sender', 'Unknown')
                subject = v.get('subject', '(제목 없음)')
                
                # 원래 메시지 블록 가져오기
                original_message = payload.get('message', {})
                original_blocks = original_message.get('blocks', [])
                
                def process_undo_silent(uid, snd, subj, resp_url, orig_blocks):
                    try:
                        from app.services.learning_store import delete_user_silent_preference, extract_email_type_pattern
                        delete_user_silent_preference(user_id=uid, sender=snd, subject=subj)
                        type_pattern = extract_email_type_pattern(subj)
                        logger.info(f"[SLACK] Deleted silent preference for {uid}, {snd}, type: {type_pattern}")
                        
                        # 원래 메시지 블록 유지하면서 상태 변경
                        new_blocks = []
                        for block in orig_blocks:
                            # 기존 context 블록 중 알림 상태 관련 메시지는 제거 (중복 방지)
                            if block.get('type') == 'context':
                                elements = block.get('elements', [])
                                if elements and ('알림 차단' in str(elements) or '알림 차단 해제됨' in str(elements)):
                                    continue
                            
                            # 기존 actions 블록을 찾아 내용물만 수정
                            if block.get('type') == 'actions':
                                new_elements = []
                                for element in block.get('elements', []):
                                    # 'Undo' 버튼을 다시 '알림 차단' 버튼으로 복구
                                    if element.get('action_id') == 'undo_silent':
                                        new_elements.append({
                                            "type": "button",
                                            "text": {"type": "plain_text", "text": "이런 알림 차단"},
                                            "style": "danger",
                                            "value": json.dumps({"sender": snd, "subject": subj}),
                                            "action_id": "silent_forever",
                                            "confirm": {
                                                "title": {"type": "plain_text", "text": "앞으로 비슷한 알림을 차단할까요?"},
                                                "text": {"type": "plain_text", "text": "이 발신자가 보내는 비슷한 메일만 알림이 꺼집니다. 다른 중요한 메일은 평소처럼 알림이 옵니다."},
                                                "confirm": {"type": "plain_text", "text": "차단"},
                                                "deny": {"type": "plain_text", "text": "취소"}
                                            }
                                        })
                                    else:
                                        # Gmail 열기, 읽음 처리 버튼은 그대로 유지
                                        new_elements.append(element)
                                block['elements'] = new_elements
                            
                            new_blocks.append(block)
                        
                        # 차단 해제 상태 메시지 추가 (actions 블록 바로 앞에 삽입)
                        final_blocks = []
                        for block in new_blocks:
                            if block.get('type') == 'actions':
                                final_blocks.append({
                                    "type": "context",
                                    "elements": [
                                        {
                                            "type": "mrkdwn",
                                            "text": "✅ *알림 차단 해제됨* — 이 발신자의 메일 알림을 다시 받습니다."
                                        }
                                    ]
                                })
                            final_blocks.append(block)
                        
                        response_data = {
                            "replace_original": True,
                            "blocks": final_blocks
                        }
                        _send_slack_response(resp_url, response_data)
                    except Exception as e:
                        logger.error(f"[SLACK] process_undo_silent error: {e}", exc_info=True)
                        if resp_url:
                            _send_slack_response(resp_url, {"text": "처리 중 오류가 발생했습니다. 다시 시도해 주세요."})

                if response_url:
                    thread = threading.Thread(target=process_undo_silent, args=(user_id, sender, subject, response_url, original_blocks))
                    thread.start()
                    return '', 200
                else:
                    from app.services.learning_store import delete_user_silent_preference
                    delete_user_silent_preference(user_id=user_id, sender=sender, subject=subject)
                    return jsonify({
                        "replace_original": True,
                        "text": f"✅ `{sender}` 발신자의 알림 차단이 해제되었습니다."
                    })
            
            elif action_id == 'mark_as_read':
                return jsonify({
                    "replace_original": True,
                    "text": "✅ 확인 완료되었습니다."
                })
            
            # open_gmail 등 URL 버튼은 별도 처리 불필요
            elif action_id == 'open_gmail':
                return '', 200
            
            elif action_id == 'mark_as_read_gmail':
                v = json.loads(action['value'])
                message_id = v.get('message_id')
                owner = v.get('owner')
                
                def process_mark_as_read(msg_id, user_email, resp_url, orig_blocks):
                    try:
                        # 1. Gmail 읽음 처리
                        success = get_gmail_service().mark_as_read(msg_id, user_email)
                        
                        if success:
                            # 2. UI 업데이트 (버튼 유지, 읽음 완료 표시만 추가)
                            new_blocks = []
                            read_context_exists = False
                            
                            for block in orig_blocks:
                                # 기존 읽음 처리 완료 context가 있으면 스킵 (중복 방지)
                                if block.get('type') == 'context':
                                    elements = block.get('elements', [])
                                    if elements and 'Gmail에서 읽음 처리' in str(elements):
                                        read_context_exists = True
                                        continue
                                new_blocks.append(block)
                            
                            # 읽음 완료 context가 없으면 actions 블록 바로 앞에 추가
                            if not read_context_exists:
                                final_blocks = []
                                for block in new_blocks:
                                    if block.get('type') == 'actions':
                                        # actions 블록 앞에 읽음 처리 완료 메시지 삽입
                                        final_blocks.append({
                                            "type": "context",
                                            "elements": [
                                                {
                                                    "type": "mrkdwn",
                                                    "text": "✅ *Gmail에서 읽음 처리되었습니다.*"
                                                }
                                            ]
                                        })
                                    final_blocks.append(block)
                                new_blocks = final_blocks
                            
                            _send_slack_response(resp_url, {"replace_original": True, "blocks": new_blocks})
                        else:
                            _send_slack_response(resp_url, {"replace_original": False, "text": "❌ 읽음 처리에 실패했습니다. 잠시 후 다시 시도해주세요."})
                            
                    except Exception as e:
                        logger.error(f"[SLACK] mark_as_read_gmail error: {e}", exc_info=True)
                        _send_slack_response(resp_url, {"replace_original": False, "text": "❌ 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."})

                if response_url:
                    thread = threading.Thread(target=process_mark_as_read, args=(message_id, owner, response_url, payload.get('message', {}).get('blocks', [])))
                    thread.start()
                    return '', 200
                
        return '', 200
    except Exception as e:
        logger.error(f"[SLACK] Error: {e}", exc_info=True)
        return '', 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
