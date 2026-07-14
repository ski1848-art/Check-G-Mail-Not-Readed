#!/usr/bin/env python3
"""
특정 사용자에 대해 발신자+유형 알림을 수동 차단하는 유틸리티 스크립트.

사용법:
  python scripts/block_sender_for_user.py \
    --user-id U02323AJ9HQ \
    --sender "jobkoinfo@jobkorea.co.kr" \
    --subject "[임원비서_지원안내]박지영님이 '[핫셀러] 경영진 비서 채용' 공고에 지원했습니다."

환경변수 필요:
  FIRESTORE_PROJECT_ID, GOOGLE_APPLICATION_CREDENTIALS (또는 gcloud 인증)
"""
import sys
import os
import argparse

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv()

from app.services.learning_store import save_user_silent_preference, extract_email_type_pattern


def main():
    parser = argparse.ArgumentParser(description="수동으로 사용자 알림 차단 규칙 추가")
    parser.add_argument("--user-id", required=True, help="Slack User ID (예: U02323AJ9HQ)")
    parser.add_argument("--sender", required=True, help="발신자 이메일 (예: jobkoinfo@jobkorea.co.kr)")
    parser.add_argument("--subject", default=None, help="원본 제목 (유형 패턴 추출용)")
    args = parser.parse_args()

    type_pattern = extract_email_type_pattern(args.subject)
    print(f"차단 정보:")
    print(f"  사용자: {args.user_id}")
    print(f"  발신자: {args.sender}")
    print(f"  추출 패턴: {type_pattern}")
    print()

    result = save_user_silent_preference(
        user_id=args.user_id,
        sender=args.sender,
        subject=args.subject
    )

    if result:
        print("✅ 차단 규칙 저장 성공!")
    else:
        print("❌ 차단 규칙 저장 실패 (Firestore 연결 또는 인증 확인 필요)")
        sys.exit(1)


if __name__ == "__main__":
    main()
