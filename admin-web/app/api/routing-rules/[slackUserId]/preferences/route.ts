/**
 * /api/routing-rules/[slackUserId]/preferences - 사용자 차단 목록 API
 * 
 * [GET]    사용자가 Slack에서 "알림 차단"한 발신자/유형 목록 조회
 * [DELETE] 관리자가 차단을 해제 (sender 쿼리 파라미터 필수)
 * 
 * Firestore user_feedback 컬렉션에서 preference="silent"인 문서를 조회.
 */
import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { getDb } from "@/lib/firebase-admin";
export async function GET(
  req: NextRequest,
  { params }: { params: { slackUserId: string } }
) {
  const session = await getServerSession();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { slackUserId } = params;
  const db = getDb();

  try {
    const snapshot = await db.collection("user_feedback")
      .where("user_id", "==", slackUserId)
      .where("preference", "==", "silent")
      .orderBy("created_at", "desc")
      .get();

    const preferences = snapshot.docs.map(doc => ({
      id: doc.id,
      ...doc.data()
    }));

    return NextResponse.json(preferences);
  } catch (error) {
    console.error("Error fetching user preferences:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}

// DELETE /api/routing-rules/[slackUserId]/preferences?sender=...
// 수신 거부 해제
export async function DELETE(
  req: NextRequest,
  { params }: { params: { slackUserId: string } }
) {
  const session = await getServerSession();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { slackUserId } = params;
  const { searchParams } = new URL(req.url);
  const sender = searchParams.get("sender");

  if (!sender) {
    return NextResponse.json({ error: "Sender is required" }, { status: 400 });
  }

  const db = getDb();

  try {
    const docId = `${slackUserId}_${sender}`;
    await db.collection("user_feedback").doc(docId).delete();

    // Audit Log 기록
    await db.collection("audit_logs").add({
      actor_email: session.user?.email,
      action: "DELETE_PREFERENCE",
      target_slack_user_id: slackUserId,
      after: { sender },
      created_at: new Date().toISOString()
    });

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Error deleting user preference:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}



