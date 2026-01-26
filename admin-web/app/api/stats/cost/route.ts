import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { getDb } from "@/lib/firebase-admin";

export const dynamic = 'force-dynamic';

// Claude Haiku 4.5 (AWS Bedrock) 가격 - 환경변수로 설정 가능
// 단위: USD per 1M tokens
const PRICING = {
  input: parseFloat(process.env.LLM_PRICE_INPUT_PER_1M || "0.80"),
  output: parseFloat(process.env.LLM_PRICE_OUTPUT_PER_1M || "4.00"),
  cacheRead: parseFloat(process.env.LLM_PRICE_CACHE_READ_PER_1M || "0.08"),
  cacheWrite: parseFloat(process.env.LLM_PRICE_CACHE_WRITE_PER_1M || "1.00"),
};

// 환율 (환경변수로 설정 가능)
const EXCHANGE_RATE = parseFloat(process.env.USD_KRW_EXCHANGE_RATE || "1350");

interface DailyStats {
  date: string;
  calls: number;
  inputTokens: number;
  outputTokens: number;
  cacheReadTokens: number;
  cacheWriteTokens: number;
  cost: number;
}

export async function GET(req: NextRequest) {
  const session = await getServerSession();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const db = getDb();
  
  try {
    // URL 파라미터에서 월 가져오기 (기본값: 현재 월)
    const searchParams = req.nextUrl.searchParams;
    const monthParam = searchParams.get('month'); // 형식: 2026-01
    
    // KST 기준으로 날짜 계산
    const kstOffset = 9 * 60 * 60 * 1000;
    const now = new Date();
    const kstNow = new Date(now.getTime() + kstOffset);
    
    let year: number, month: number;
    if (monthParam) {
      const [y, m] = monthParam.split('-').map(Number);
      year = y;
      month = m - 1; // JavaScript month is 0-indexed
    } else {
      year = kstNow.getFullYear();
      month = kstNow.getMonth();
    }
    
    // 해당 월의 시작과 끝 계산 (KST)
    const monthStart = new Date(Date.UTC(year, month, 1, -9, 0, 0)); // KST 00:00 -> UTC
    const monthEnd = new Date(Date.UTC(year, month + 1, 1, -9, 0, 0)); // 다음 달 KST 00:00 -> UTC
    
    // Firestore에서 해당 월의 email_events 조회
    const eventsSnapshot = await db.collection("email_events")
      .where("created_at", ">=", monthStart)
      .where("created_at", "<", monthEnd)
      .get();
    
    // 토큰 집계
    let totalInputTokens = 0;
    let totalOutputTokens = 0;
    let totalCacheReadTokens = 0;
    let totalCacheWriteTokens = 0;
    let totalCalls = 0;
    
    // 일별 집계를 위한 맵
    const dailyMap = new Map<string, DailyStats>();
    
    eventsSnapshot.docs.forEach(doc => {
      const data = doc.data();
      
      // 토큰 필드가 있는 경우만 집계 (LLM 호출이 있었던 경우)
      const inputTokens = data.llm_input_tokens || 0;
      const outputTokens = data.llm_output_tokens || 0;
      const cacheReadTokens = data.llm_cache_read_tokens || 0;
      const cacheWriteTokens = data.llm_cache_write_tokens || 0;
      
      // 토큰이 하나라도 있으면 LLM 호출로 카운트
      if (inputTokens > 0 || outputTokens > 0) {
        totalCalls++;
        totalInputTokens += inputTokens;
        totalOutputTokens += outputTokens;
        totalCacheReadTokens += cacheReadTokens;
        totalCacheWriteTokens += cacheWriteTokens;
        
        // 일별 집계
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
        
        if (!dailyMap.has(dateStr)) {
          dailyMap.set(dateStr, {
            date: dateStr,
            calls: 0,
            inputTokens: 0,
            outputTokens: 0,
            cacheReadTokens: 0,
            cacheWriteTokens: 0,
            cost: 0,
          });
        }
        
        const daily = dailyMap.get(dateStr)!;
        daily.calls++;
        daily.inputTokens += inputTokens;
        daily.outputTokens += outputTokens;
        daily.cacheReadTokens += cacheReadTokens;
        daily.cacheWriteTokens += cacheWriteTokens;
      }
    });
    
    // 비용 계산 함수
    const calculateCost = (input: number, output: number, cacheRead: number, cacheWrite: number) => {
      const inputCost = (input / 1_000_000) * PRICING.input;
      const outputCost = (output / 1_000_000) * PRICING.output;
      const cacheReadCost = (cacheRead / 1_000_000) * PRICING.cacheRead;
      const cacheWriteCost = (cacheWrite / 1_000_000) * PRICING.cacheWrite;
      return inputCost + outputCost + cacheReadCost + cacheWriteCost;
    };
    
    // 총 비용 계산
    const totalCostUSD = calculateCost(
      totalInputTokens,
      totalOutputTokens,
      totalCacheReadTokens,
      totalCacheWriteTokens
    );
    
    // 일별 비용 계산 및 정렬
    const dailyBreakdown: DailyStats[] = [];
    dailyMap.forEach((stats) => {
      stats.cost = calculateCost(
        stats.inputTokens,
        stats.outputTokens,
        stats.cacheReadTokens,
        stats.cacheWriteTokens
      );
      dailyBreakdown.push(stats);
    });
    dailyBreakdown.sort((a, b) => a.date.localeCompare(b.date));
    
    // 캐시 적중률 계산
    const totalInput = totalInputTokens + totalCacheReadTokens;
    const cacheHitRate = totalInput > 0 ? (totalCacheReadTokens / totalInput) * 100 : 0;
    
    // 응답 생성
    const response = {
      period: `${year}-${String(month + 1).padStart(2, '0')}`,
      totalCalls,
      totalEvents: eventsSnapshot.size,
      tokens: {
        input: totalInputTokens,
        output: totalOutputTokens,
        cacheRead: totalCacheReadTokens,
        cacheWrite: totalCacheWriteTokens,
      },
      cost: {
        input: Math.round((totalInputTokens / 1_000_000) * PRICING.input * 100) / 100,
        output: Math.round((totalOutputTokens / 1_000_000) * PRICING.output * 100) / 100,
        cacheRead: Math.round((totalCacheReadTokens / 1_000_000) * PRICING.cacheRead * 100) / 100,
        cacheWrite: Math.round((totalCacheWriteTokens / 1_000_000) * PRICING.cacheWrite * 100) / 100,
        totalUSD: Math.round(totalCostUSD * 100) / 100,
        totalKRW: Math.round(totalCostUSD * EXCHANGE_RATE),
      },
      cacheHitRate: Math.round(cacheHitRate * 10) / 10,
      pricing: PRICING,
      exchangeRate: EXCHANGE_RATE,
      dailyBreakdown,
      lastUpdated: new Date().toISOString(),
      note: "비용은 예상치입니다. 실제 청구 금액은 AWS 콘솔에서 확인하세요.",
    };
    
    return NextResponse.json(response);
  } catch (error) {
    console.error("Error fetching cost stats:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}
