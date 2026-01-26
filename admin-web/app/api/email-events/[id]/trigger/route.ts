import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { getDb } from "@/lib/firebase-admin";

// Flask 서비스 URL (환경변수에서 가져오거나 기본값 사용)
const FLASK_SERVICE_URL = process.env.FLASK_SERVICE_URL || "https://gmail-notifier-165856206700.asia-northeast3.run.app";

// POST /api/email-events/[id]/trigger
// 관리자가 수동으로 특정 메일의 알림을 전송하도록 요청
export async function POST(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  const session = await getServerSession();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const email_id = params.id;
  const db = getDb();

  try {
    // 1. 해당 메일 이벤트 정보 조회 (대상자 확인용)
    const doc = await db.collection("email_events").doc(email_id).get();
    if (!doc.exists) {
      return NextResponse.json({ error: "Event not found" }, { status: 404 });
    }

    const eventData = doc.data();
    
    // 2. Flask 백엔드로 알림 전송 요청
    const response = await fetch(`${FLASK_SERVICE_URL}/trigger-notification`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        email_id: email_id,
        target_ids: eventData?.slack_targets || []
      }),
    });

    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.message || "Failed to trigger notification on backend");
    }

    // 3. Audit Log 기록
    await db.collection("audit_logs").add({
      actor_email: session.user?.email,
      action: "MANUAL_NOTIFICATION_TRIGGER",
      target_email_id: email_id,
      subject: eventData?.subject,
      created_at: new Date().toISOString()
    });

    return NextResponse.json({ success: true, message: "Notification triggered" });
  } catch (error: any) {
    console.error("Error triggering manual notification:", error);
    return NextResponse.json({ error: error.message || "Internal Server Error" }, { status: 500 });
  }
}
