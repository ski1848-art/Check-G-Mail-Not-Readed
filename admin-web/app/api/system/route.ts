import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { getDb } from "@/lib/firebase-admin";

export const dynamic = 'force-dynamic';

const SYSTEM_CONTROL_COLLECTION = "system_control";
const SYSTEM_CONTROL_DOC = "status";
const DAILY_USAGE_COLLECTION = "daily_usage";

// 백엔드 서비스 URL
const BACKEND_URL = process.env.BACKEND_SERVICE_URL || "https://gmail-notifier-165856206700.asia-northeast3.run.app";

/**
 * GET /api/system - 시스템 상태 조회
 */
export async function GET(req: NextRequest) {
  const session = await getServerSession();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const db = getDb();
  
  try {
    // 1. 시스템 상태 조회
    const statusDoc = await db.collection(SYSTEM_CONTROL_COLLECTION).doc(SYSTEM_CONTROL_DOC).get();
    const statusData = statusDoc.exists ? statusDoc.data() : {};
    
    // 2. 오늘 일일 사용량 조회 (KST 기준)
    const kstOffset = 9 * 60 * 60 * 1000;
    const now = new Date();
    const kstNow = new Date(now.getTime() + kstOffset);
    const today = kstNow.toISOString().split('T')[0];
    
    const usageDoc = await db.collection(DAILY_USAGE_COLLECTION).doc(today).get();
    const usageData = usageDoc.exists ? usageDoc.data() : {};
    
    return NextResponse.json({
      // 시스템 상태
      enabled: statusData?.enabled ?? true,
      pausedAt: statusData?.paused_at || null,
      pausedBy: statusData?.paused_by || null,
      pauseReason: statusData?.pause_reason || null,
      
      // 일일 한도
      dailyLimitCalls: statusData?.daily_limit_calls ?? 1000,
      dailyLimitCostUsd: statusData?.daily_limit_cost_usd ?? 5.0,
      
      // 마지막 배치 정보
      lastBatchAt: statusData?.last_batch_at || null,
      lastBatchProcessed: statusData?.last_batch_processed ?? 0,
      
      // 오늘 사용량
      todayUsage: {
        date: today,
        calls: usageData?.calls ?? 0,
        costUsd: usageData?.cost_usd ?? 0,
        inputTokens: usageData?.input_tokens ?? 0,
        outputTokens: usageData?.output_tokens ?? 0,
      },
      
      lastUpdated: new Date().toISOString(),
    });
  } catch (error) {
    console.error("Error fetching system status:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}

/**
 * POST /api/system - 시스템 제어 (중지/재시작/수동 실행)
 */
export async function POST(req: NextRequest) {
  const session = await getServerSession();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const db = getDb();
  const body = await req.json();
  const { action, reason, dailyLimitCalls, dailyLimitCostUsd } = body;
  
  try {
    const userEmail = session.user?.email || "unknown";
    const now = new Date().toISOString();
    
    switch (action) {
      case "pause": {
        // 시스템 일시 중지
        await db.collection(SYSTEM_CONTROL_COLLECTION).doc(SYSTEM_CONTROL_DOC).set({
          enabled: false,
          paused_at: now,
          paused_by: userEmail,
          pause_reason: reason || "관리자가 수동으로 일시 중지",
          updated_at: now,
          updated_by: userEmail,
        }, { merge: true });
        
        console.log(`[SYSTEM] Paused by ${userEmail}. Reason: ${reason}`);
        return NextResponse.json({ success: true, message: "시스템이 일시 중지되었습니다." });
      }
      
      case "resume": {
        // 시스템 재시작
        await db.collection(SYSTEM_CONTROL_COLLECTION).doc(SYSTEM_CONTROL_DOC).set({
          enabled: true,
          paused_at: null,
          paused_by: null,
          pause_reason: null,
          updated_at: now,
          updated_by: userEmail,
        }, { merge: true });
        
        console.log(`[SYSTEM] Resumed by ${userEmail}`);
        return NextResponse.json({ success: true, message: "시스템이 재시작되었습니다." });
      }
      
      case "run_batch": {
        // 수동 배치 실행
        try {
          const response = await fetch(`${BACKEND_URL}/run-batch`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
          });
          const result = await response.json();
          
          console.log(`[SYSTEM] Manual batch triggered by ${userEmail}. Result:`, result);
          return NextResponse.json({ 
            success: true, 
            message: `배치 실행 완료: ${result.processed || 0}건 처리`,
            result 
          });
        } catch (error) {
          console.error("Error triggering batch:", error);
          return NextResponse.json({ 
            success: false, 
            message: "배치 실행 실패. 백엔드 서비스를 확인하세요." 
          }, { status: 500 });
        }
      }
      
      case "set_limits": {
        // 일일 한도 설정
        const updates: Record<string, unknown> = {
          updated_at: now,
          updated_by: userEmail,
        };
        
        if (dailyLimitCalls !== undefined) {
          updates.daily_limit_calls = dailyLimitCalls;
        }
        if (dailyLimitCostUsd !== undefined) {
          updates.daily_limit_cost_usd = dailyLimitCostUsd;
        }
        
        await db.collection(SYSTEM_CONTROL_COLLECTION).doc(SYSTEM_CONTROL_DOC).set(updates, { merge: true });
        
        console.log(`[SYSTEM] Limits updated by ${userEmail}:`, { dailyLimitCalls, dailyLimitCostUsd });
        return NextResponse.json({ success: true, message: "일일 한도가 업데이트되었습니다." });
      }
      
      default:
        return NextResponse.json({ error: "Invalid action" }, { status: 400 });
    }
  } catch (error) {
    console.error("Error controlling system:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}

