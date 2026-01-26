import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { getDb } from "@/lib/firebase-admin";

const FLASK_SERVICE_URL = process.env.FLASK_SERVICE_URL || "https://gmail-notifier-165856206700.asia-northeast3.run.app";

// POST /api/email-events/[id]/block
// 관리자가 수동으로 특정 메일을 차단하고 학습시키도록 요청
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
      return NextResponse.json({ error: "Event not found" }, { status: 404 });
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
      throw new Error(result.message || "Failed to block notification on backend");
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
