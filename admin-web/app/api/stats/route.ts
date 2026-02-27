import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { getDb } from "@/lib/firebase-admin";

export const dynamic = 'force-dynamic';

const BACKEND_URL = process.env.BACKEND_SERVICE_URL || "https://gmail-notifier-165856206700.asia-northeast3.run.app";

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

    // 3. 최근 30일 평균 통계 계산
    const daysToAnalyze = 30;
    const kstDaysAgoStart = new Date(kstNow.getFullYear(), kstNow.getMonth(), kstNow.getDate() - daysToAnalyze);
    const daysAgoStart = new Date(kstDaysAgoStart.getTime() - kstOffset);
    
    const recentEventsSnapshot = await db.collection("email_events")
      .where("timestamp", ">=", daysAgoStart)
      .get();
    
    // 일별 집계
    const dailyStatsMap = new Map<string, { total: number; aiDetected: number }>();
    
    recentEventsSnapshot.docs.forEach(doc => {
      const data = doc.data();
      
      // 날짜 추출 (KST 기준)
      let dateStr: string;
      if (data.created_at && data.created_at.toDate) {
        const eventDate = new Date(data.created_at.toDate().getTime() + kstOffset);
        dateStr = eventDate.toISOString().split('T')[0];
      } else if (data.timestamp && data.timestamp.toDate) {
        const eventDate = new Date(data.timestamp.toDate().getTime() + kstOffset);
        dateStr = eventDate.toISOString().split('T')[0];
      } else {
        return; // 날짜 정보 없으면 스킵
      }
      
      // 일별 통계 초기화
      if (!dailyStatsMap.has(dateStr)) {
        dailyStatsMap.set(dateStr, { total: 0, aiDetected: 0 });
      }
      
      const dailyStats = dailyStatsMap.get(dateStr)!;
      dailyStats.total++;
      
      // AI 검출 여부 확인 (LLM 토큰이 있으면 AI 검출로 간주)
      const hasAiDetection = (data.llm_input_tokens || 0) > 0 || (data.llm_output_tokens || 0) > 0;
      if (hasAiDetection) {
        dailyStats.aiDetected++;
      }
    });
    
    // 평균 계산
    const dailyStatsArray = Array.from(dailyStatsMap.values());
    const avgDailyProcessed = dailyStatsArray.length > 0 
      ? Math.round(dailyStatsArray.reduce((sum, stats) => sum + stats.total, 0) / dailyStatsArray.length)
      : 0;
    const avgDailyAiDetected = dailyStatsArray.length > 0
      ? Math.round(dailyStatsArray.reduce((sum, stats) => sum + stats.aiDetected, 0) / dailyStatsArray.length)
      : 0;

    // 4. AI 판단 정확도 (예측값 - 이 데이터는 학습 데이터가 더 쌓여야 의미가 있지만 일단 구색을 맞춤)
    // 여기서는 간단히 전체 대비 알림 비중 등을 보냄
    
    let systemStatus = "Healthy";
    if (process.env.FEATURE_REAL_HEALTH_STATUS === "true") {
      try {
        const healthRes = await fetch(`${BACKEND_URL}/health`, { cache: "no-store" });
        systemStatus = healthRes.ok ? "Healthy" : "Degraded";
      } catch (e) {
        systemStatus = "Degraded";
      }
    }

    return NextResponse.json({
      totalUsers,
      activeUsers,
      totalProcessedToday,
      notifiedToday,
      silencedToday,
      systemStatus,
      averages: {
        dailyProcessed: avgDailyProcessed,
        dailyAiDetected: avgDailyAiDetected,
        periodDays: dailyStatsArray.length || daysToAnalyze
      },
      lastUpdated: new Date().toISOString()
    });
  } catch (error) {
    console.error("Error fetching stats:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}


