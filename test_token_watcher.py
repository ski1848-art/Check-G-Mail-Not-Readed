"""Token-Watcher 연결 테스트 스크립트"""
import httpx
import json
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN_WATCHER_URL = os.environ.get("TOKEN_WATCHER_URL", "https://j5kbufu9o2.execute-api.ap-northeast-2.amazonaws.com")
TOKEN_WATCHER_KEY = os.environ.get("TOKEN_WATCHER_KEY", "")

def test_token_watcher():
    print(f"Token-Watcher URL: {TOKEN_WATCHER_URL}")
    print(f"Token-Watcher Key: {TOKEN_WATCHER_KEY[:10]}...")
    print()

    payload = {
        "provider": "bedrock",
        "model_id": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "stream": True,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant. Reply in Korean."},
            {"role": "user", "content": "안녕하세요. 테스트 메시지입니다. 짧게 응답해주세요."},
        ],
        "max_tokens": 100,
        "temperature": 0.0,
    }

    print("Token-Watcher 호출 중...")
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{TOKEN_WATCHER_URL}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {TOKEN_WATCHER_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        print(f"HTTP 상태코드: {response.status_code}")
        print(f"응답 헤더: {dict(response.headers)}")
        print()

        if response.status_code == 200:
            data = response.json()
            print("✅ 성공!")
            print(f"응답 전체: {json.dumps(data, ensure_ascii=False, indent=2)}")
            try:
                text = data["output"]["message"]["content"][0]["text"]
                print(f"\nLLM 응답 텍스트: {text}")
            except (KeyError, IndexError) as e:
                print(f"응답 파싱 실패: {e}")
        else:
            print(f"❌ 실패: {response.text}")

    except httpx.ConnectError as e:
        print(f"❌ 연결 실패: {e}")
    except httpx.TimeoutException as e:
        print(f"❌ 타임아웃: {e}")
    except Exception as e:
        print(f"❌ 오류: {e}")

if __name__ == "__main__":
    test_token_watcher()
