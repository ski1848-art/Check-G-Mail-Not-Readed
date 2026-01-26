import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { getDb } from "@/lib/firebase-admin";

export const dynamic = 'force-dynamic';

export async function GET(req: NextRequest) {
  const session = await getServerSession();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const db = getDb();
  
  try {
    // KST(UTC+9) 기준으로 '오늘' 시작 시각 계산
    const now = new Date();
    const kstOffset = 9 * 60 * 60 * 1000;
    const kstNow = new Date(now.getTime() + kstOffset);
    
    // KST 날짜의 00:00:00 계산
    const kstTodayStart = new Date(kstNow.getFullYear(), kstNow.getMonth(), kstNow.getDate());
    // 다시 UTC로 변환하여 Firestore 쿼리에 사용
    const todayStart = new Date(kstTodayStart.getTime() - kstOffset);
    
    // 1. 전체 사용자 수
    const usersSnapshot = await db.collection("routing_rules").get();
    const totalUsers = usersSnapshot.size;
    const activeUsers = usersSnapshot.docs.filter(doc => doc.data().enabled !== false).length;

    // 2. 오늘 처리된 메일 수 (timestamp 기준 - 실제 메일 수신 시각)
    // created_at이 누락된 예전 데이터를 위해 timestamp도 함께 체크
    const todayEventsSnapshot = await db.collection("email_events")
      .where("timestamp", ">=", todayStart)
      .get();
    
    // 로그로 데이터 수 확인 (Cloud Run 로그에서 확인 가능)
    console.log(`[STATS] Found ${todayEventsSnapshot.size} events for today since ${todayStart.toISOString()}`);
    
    const totalProcessedToday = todayEventsSnapshot.size;
    const notifiedToday = todayEventsSnapshot.docs.filter(doc => doc.data().final_category === 'notify').length;
    const silencedToday = totalProcessedToday - notifiedToday;

    // 3. AI 판단 정확도 (예측값 - 이 데이터는 학습 데이터가 더 쌓여야 의미가 있지만 일단 구색을 맞춤)
    // 여기서는 간단히 전체 대비 알림 비중 등을 보냄
    
    return NextResponse.json({
      totalUsers,
      activeUsers,
      totalProcessedToday,
      notifiedToday,
      silencedToday,
      systemStatus: "Healthy",
      lastUpdated: new Date().toISOString()
    });
  } catch (error) {
    console.error("Error fetching stats:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}



