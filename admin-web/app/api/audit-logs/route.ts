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
