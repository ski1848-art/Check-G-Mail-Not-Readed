/**
 * GET /api/routing-rules/[slackUserId]/history - 사용자별 알림 이력 조회
 * 
 * 특정 Slack 사용자에게 전송된 최근 50건의 이메일 알림 이력을 반환.
 * Firestore email_events에서 slack_targets 배열에 해당 사용자 ID가 포함된 문서를 조회.
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
    // email_events에서 이 사용자가 포함된 최근 50개 알림 조회
    const snapshot = await db.collection("email_events")
      .where("slack_targets", "array-contains", slackUserId)
      .orderBy("created_at", "desc")
      .limit(50)
      .get();

    const history = snapshot.docs.map(doc => ({
      id: doc.id,
      ...doc.data()
    }));

    return NextResponse.json(history);
  } catch (error) {
    console.error("Error fetching notification history:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}



