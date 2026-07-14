/**
 * GET /api/audit-logs - 감사 로그 조회 API
 * 
 * Firestore audit_logs 컬렉션에서 최근 200건의 변경 이력을 반환.
 * 사용자 생성/수정/삭제, 설정 변경, 수동 알림 전송/차단 등 모든 관리 작업이 기록됨.
 */
import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { getDb } from "@/lib/firebase-admin";

// Force dynamic rendering
export const dynamic = 'force-dynamic';

export async function GET(req: NextRequest) {
  const db = getDb();
  const session = await getServerSession();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  try {
    const snapshot = await db.collection("audit_logs")
      .orderBy("created_at", "desc")
      .limit(200)
      .get();
    
    const logs = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
    return NextResponse.json(logs);
  } catch (error) {
    console.error("Error fetching audit logs:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}
