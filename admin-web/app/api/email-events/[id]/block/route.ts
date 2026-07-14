/**
 * POST /api/email-events/[id]/block - 수동 차단 + 학습 API
 * 
 * 관리자가 모니터링 페이지에서 "앞으로 차단" 버튼 클릭 시 호출.
 * Flask 백엔드의 /block-notification 엔드포인트로 요청을 프록시.
 * 
 * [동작]
 *   1. Firestore에서 해당 이메일 이벤트 조회
 *   2. Flask 백엔드로 차단 요청 (발신자+유형 패턴 학습)
 *   3. audit_logs에 MANUAL_NOTIFICATION_BLOCK 기록
 */
import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { getDb } from "@/lib/firebase-admin";
import { FLASK_SERVICE_URL } from "@/lib/constants";

export async function POST(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  const session = await getServerSession();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const email_id = params.id;
  const db = getDb();

  try {
    const doc = await db.collection("email_events").doc(email_id).get();
    if (!doc.exists) {
      return NextResponse.json({ error: "메일 정보를 찾을 수 없습니다" }, { status: 404 });
    }

    const eventData = doc.data();
    
    // Flask 백엔드로 차단 및 학습 요청
    const response = await fetch(`${FLASK_SERVICE_URL}/block-notification`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        email_id: email_id
      }),
    });

    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.message || "차단 처리에 실패했습니다");
    }

    // Audit Log 기록
    await db.collection("audit_logs").add({
      actor_email: session.user?.email,
      action: "MANUAL_NOTIFICATION_BLOCK",
      target_email_id: email_id,
      subject: eventData?.subject,
      created_at: new Date().toISOString()
    });

    return NextResponse.json({ success: true, message: "Notification blocked and learned" });
  } catch (error: any) {
    console.error("Error blocking manual notification:", error);
    return NextResponse.json({ error: error.message || "Internal Server Error" }, { status: 500 });
  }
}
