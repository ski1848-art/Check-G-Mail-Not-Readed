#!/usr/bin/env python3
"""
하루 평균 메일 확인 수 및 AI 검출 수를 확인하는 스크립트
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from collections import defaultdict

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.state_store import FirestoreStateStore

def check_daily_average():
    """최근 30일간의 일별 평균 통계를 계산하고 출력"""
    try:
        store = FirestoreStateStore()
        db = store.db
        
        if not db:
            print("❌ Firestore 연결 실패")
            return
        
        # KST(UTC+9) 기준으로 날짜 계산
        kst = timezone(timedelta(hours=9))
        now = datetime.now(kst)
        
        # 최근 30일 데이터 조회
        days_to_analyze = 30
        days_ago_start = now - timedelta(days=days_to_analyze)
        days_ago_start_utc = days_ago_start.astimezone(timezone.utc)
        
        print(f"\n📊 최근 {days_to_analyze}일간 통계 분석 중...")
        print(f"기간: {days_ago_start.date()} ~ {now.date()} (KST)\n")
        
        # Firestore에서 이벤트 조회
        events_ref = db.collection("email_events")
        events_query = events_ref.where("timestamp", ">=", days_ago_start_utc)
        events_snapshot = events_query.stream()
        
        events_list = list(events_snapshot)
        print(f"총 이벤트 수: {len(events_list)}건\n")
        
        # 일별 집계
        daily_stats = defaultdict(lambda: {"total": 0, "ai_detected": 0})
        
        for doc in events_list:
            data = doc.to_dict()
            
            # 날짜 추출 (KST 기준)
            date_str = None
            if "created_at" in data and data["created_at"]:
                if hasattr(data["created_at"], "timestamp"):
                    event_date = datetime.fromtimestamp(data["created_at"].timestamp(), tz=kst)
                else:
                    event_date = data["created_at"].astimezone(kst)
                date_str = event_date.date().isoformat()
            elif "timestamp" in data and data["timestamp"]:
                if hasattr(data["timestamp"], "timestamp"):
                    event_date = datetime.fromtimestamp(data["timestamp"].timestamp(), tz=kst)
                else:
                    event_date = data["timestamp"].astimezone(kst)
                date_str = event_date.date().isoformat()
            
            if not date_str:
                continue
            
            # 일별 통계 업데이트
            daily_stats[date_str]["total"] += 1
            
            # AI 검출 여부 확인 (LLM 토큰이 있으면 AI 검출로 간주)
            has_ai_detection = (
                (data.get("llm_input_tokens") or 0) > 0 or
                (data.get("llm_output_tokens") or 0) > 0
            )
            if has_ai_detection:
                daily_stats[date_str]["ai_detected"] += 1
        
        # 평균 계산
        daily_stats_list = sorted(daily_stats.items())
        
        if not daily_stats_list:
            print("❌ 데이터가 없습니다.")
            return
        
        total_processed = sum(stats["total"] for _, stats in daily_stats_list)
        total_ai_detected = sum(stats["ai_detected"] for _, stats in daily_stats_list)
        
        avg_daily_processed = round(total_processed / len(daily_stats_list))
        avg_daily_ai_detected = round(total_ai_detected / len(daily_stats_list))
        
        # 결과 출력
        print("=" * 60)
        print("📈 하루 평균 통계")
        print("=" * 60)
        print(f"\n✅ 하루 평균 메일 확인 수: {avg_daily_processed:,}통")
        print(f"🤖 하루 평균 AI 검출 수: {avg_daily_ai_detected:,}통")
        print(f"\n📅 집계 기간: {len(daily_stats_list)}일")
        print(f"📊 총 처리 메일: {total_processed:,}통")
        print(f"🤖 총 AI 검출: {total_ai_detected:,}통")
        
        if daily_stats_list:
            print(f"\n📊 일별 상세 통계 (최근 10일):")
            print("-" * 60)
            for date_str, stats in daily_stats_list[-10:]:
                percentage = (stats["ai_detected"] / stats["total"] * 100) if stats["total"] > 0 else 0
                print(
                    f"{date_str}: 전체 {stats['total']:4d}통 | "
                    f"AI {stats['ai_detected']:4d}통 ({percentage:5.1f}%)"
                )
        
        print("\n" + "=" * 60 + "\n")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    check_daily_average()
