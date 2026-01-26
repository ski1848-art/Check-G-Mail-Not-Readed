import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { getDb } from "@/lib/firebase-admin";

export const dynamic = 'force-dynamic';

// GET /api/email-events
// 전체 메일 처리 이력 조회 (모니터링용)
export async function GET(req: NextRequest) {
  const session = await getServerSession();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { searchParams } = new URL(req.url);
  const limit = parseInt(searchParams.get("limit") || "50");
  const category = searchParams.get("category"); // 'notify' or 'silent'
  const date = searchParams.get("date"); // 'YYYY-MM-DD'
  
  const db = getDb();
  
  try {
    // 1. 사용자 이름 매핑 정보 가져오기
    const usersSnapshot = await db.collection("routing_rules").get();
    const userMap: Record<string, string> = {};
    usersSnapshot.docs.forEach(doc => {
      const data = doc.data();
      userMap[doc.id] = data.slack_display_name || doc.id;
    });

    // 2. 이메일 이벤트 가져오기
    let query: any = db.collection("email_events")
      .orderBy("timestamp", "desc");

    let snapshot;
    try {
      if (category && category !== 'all') {
        query = query.where("final_category", "==", category);
      }

      if (date) {
        const startOfDay = new Date(`${date}T00:00:00Z`);
        const endOfDay = new Date(`${date}T23:59:59.999Z`);
        query = query.where("timestamp", ">=", startOfDay).where("timestamp", "<=", endOfDay);
      }

      snapshot = await query.limit(limit).get();
    } catch (queryError: any) {
      console.warn("Firestore query failed, falling back to in-memory filtering:", queryError.message);
      
      // 인덱스 오류일 경우 기본 쿼리(최근 500개)를 가져와서 메모리에서 필터링
      let fallbackQuery = db.collection("email_events").orderBy("timestamp", "desc").limit(500);
      snapshot = await fallbackQuery.get();
      
      let filteredDocs = snapshot.docs;
      if (category && category !== 'all') {
        filteredDocs = filteredDocs.filter((d: any) => d.data().final_category === category);
      }
      if (date) {
        filteredDocs = filteredDocs.filter((d: any) => {
          const data = d.data();
          let ts = data.timestamp;
          if (ts && typeof ts.toDate === 'function') ts = ts.toDate();
          if (!ts) return false;
          // KST 기준 날짜 체크 (date는 'YYYY-MM-DD' 형식)
          const dStr = new Date(ts.getTime() + (9 * 60 * 60 * 1000)).toISOString().split('T')[0];
          return dStr === date;
        });
      }
      
      return NextResponse.json(filteredDocs.slice(0, limit).map(doc => {
        const data = doc.data();
        let timestamp = data.timestamp;
        if (timestamp && typeof timestamp.toDate === 'function') {
          timestamp = timestamp.toDate().toISOString();
        }
        return {
          id: doc.id,
          ...data,
          timestamp,
          slack_targets_with_names: (data.slack_targets || []).map((id: string) => ({
            id,
            name: userMap[id] || id
          }))
        };
      }));
    }

    const events = snapshot.docs.map((doc: any) => {
      const data = doc.data();
      let timestamp = data.timestamp;
      if (timestamp && typeof timestamp.toDate === 'function') {
        timestamp = timestamp.toDate().toISOString();
      }

      return {
        id: doc.id,
        ...data,
        timestamp,
        slack_targets_with_names: (data.slack_targets || []).map((id: string) => ({
          id,
          name: userMap[id] || id
        }))
      };
    });

    return NextResponse.json(events);
  } catch (error) {
    console.error("Error fetching email events:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}
