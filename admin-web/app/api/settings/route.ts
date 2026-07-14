/**
 * /api/settings - 시스템 전역 설정 API
 * 
 * [GET]  현재 설정값 조회 (Firestore system_settings/general)
 * [PUT]  설정값 업데이트 (merge 방식, audit_logs에 변경 전/후 기록)
 * 
 * [설정 항목]
 *   - score_threshold_notify: AI 알림 임계값 (0.0~1.0)
 *   - routing_cache_ttl: 라우팅 캐시 TTL (초)
 *   - blacklist_domains[]: 차단 도메인 목록
 *   - whitelist_domains[]: 우선 알림 도메인 목록
 *   - spam_keywords[]: 스팸 키워드 (제목에 포함 시 즉시 SILENT)
 *   - urgent_keywords[]: 긴급 키워드 (제목에 포함 시 즉시 NOTIFY)
 */
import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { getDb } from "@/lib/firebase-admin";
import { SETTINGS_COLLECTION, SETTINGS_DOC } from "@/lib/constants";

// 기본 설정값
const DEFAULT_SETTINGS = {
  score_threshold_notify: 0.7,
  routing_cache_ttl: 60,
  blacklist_domains: [
    "mail.notion.so", "notion.so", "promotions.google.com", 
    "no-reply.facebook.com", "workspace-noreply@google.com"
  ],
  whitelist_domains: ["important-client.com", "investor.com"],
  spam_keywords: ["광고", "뉴스레터", "무료 체험", "unsubscribe"],
  urgent_keywords: ["긴급", "장애", "계약", "제안서", "투자", "견적서"]
};

// GET /api/settings
export async function GET(req: NextRequest) {
  const session = await getServerSession();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const db = getDb();
  
  try {
    const doc = await db.collection(SETTINGS_COLLECTION).doc(SETTINGS_DOC).get();
    
    if (!doc.exists) {
      return NextResponse.json(DEFAULT_SETTINGS);
    }

    return NextResponse.json(doc.data());
  } catch (error) {
    console.error("Error fetching settings:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}

// PUT /api/settings
export async function PUT(req: NextRequest) {
  const session = await getServerSession();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const db = getDb();
  const body = await req.json();
  
  try {
    const docRef = db.collection(SETTINGS_COLLECTION).doc(SETTINGS_DOC);
    const before = (await docRef.get()).data() || {};
    
    const updatedSettings = {
      ...body,
      updated_at: new Date().toISOString(),
      updated_by: session.user?.email
    };

    await docRef.set(updatedSettings, { merge: true });

    // Audit Log 기록
    await db.collection("audit_logs").add({
      actor_email: session.user?.email,
      action: "UPDATE_SYSTEM_SETTINGS",
      before,
      after: updatedSettings,
      created_at: new Date().toISOString()
    });

    return NextResponse.json({ success: true, settings: updatedSettings });
  } catch (error) {
    console.error("Error updating settings:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}

