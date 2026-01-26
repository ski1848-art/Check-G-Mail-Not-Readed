import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { getDb } from "@/lib/firebase-admin";
import { FieldValue } from "firebase-admin/firestore";

// Force dynamic rendering
export const dynamic = 'force-dynamic';

export async function GET(req: NextRequest) {
  const db = getDb();
  const session = await getServerSession();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  try {
    const snapshot = await db.collection("routing_rules").orderBy("updated_at", "desc").get();
    const rules = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
    return NextResponse.json(rules);
  } catch (error) {
    console.error("Error fetching routing rules:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}

export async function POST(req: NextRequest) {
  const db = getDb();
  const session = await getServerSession();
  if (!session || !session.user?.email) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  try {
    const body = await req.json();
    const { slack_user_id, slack_display_name, gmail_accounts, enabled } = body;

    // Validation
    if (!slack_user_id || !/^U[A-Z0-9]+$/.test(slack_user_id)) {
      return NextResponse.json({ error: "Invalid Slack User ID" }, { status: 400 });
    }
    if (!Array.isArray(gmail_accounts)) {
      return NextResponse.json({ error: "gmail_accounts must be an array" }, { status: 400 });
    }

    const data = {
      slack_user_id,
      slack_display_name: slack_display_name || "",
      gmail_accounts: gmail_accounts.map((e: string) => e.toLowerCase().trim()),
      enabled: enabled ?? true,
      created_at: FieldValue.serverTimestamp(),
      updated_at: FieldValue.serverTimestamp(),
      created_by: session.user.email,
      updated_by: session.user.email,
    };

    await db.collection("routing_rules").doc(slack_user_id).set(data);

    // Audit Log
    await db.collection("audit_logs").add({
      actor_email: session.user.email,
      action: "CREATE",
      target_slack_user_id: slack_user_id,
      after: data,
      created_at: FieldValue.serverTimestamp(),
    });

    return NextResponse.json({ success: true, id: slack_user_id });
  } catch (error) {
    console.error("Error creating routing rule:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}
