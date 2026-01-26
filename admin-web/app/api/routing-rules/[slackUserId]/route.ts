import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { getDb } from "@/lib/firebase-admin";
import { FieldValue } from "firebase-admin/firestore";

// Force dynamic rendering
export const dynamic = 'force-dynamic';

export async function GET(req: NextRequest, { params }: { params: { slackUserId: string } }) {
  const db = getDb();
  const session = await getServerSession();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  try {
    const doc = await db.collection("routing_rules").doc(params.slackUserId).get();
    if (!doc.exists) return NextResponse.json({ error: "Not Found" }, { status: 404 });
    return NextResponse.json({ id: doc.id, ...doc.data() });
  } catch (error) {
    console.error("Error fetching routing rule:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}

export async function PUT(req: NextRequest, { params }: { params: { slackUserId: string } }) {
  const db = getDb();
  const session = await getServerSession();
  if (!session || !session.user?.email) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  try {
    const body = await req.json();
    const { slack_display_name, gmail_accounts, enabled } = body;

    const docRef = db.collection("routing_rules").doc(params.slackUserId);
    const oldDoc = await docRef.get();
    if (!oldDoc.exists) return NextResponse.json({ error: "Not Found" }, { status: 404 });

    const updateData: any = {
      updated_at: FieldValue.serverTimestamp(),
      updated_by: session.user.email,
    };

    if (slack_display_name !== undefined) updateData.slack_display_name = slack_display_name;
    if (gmail_accounts !== undefined) updateData.gmail_accounts = gmail_accounts.map((e: string) => e.toLowerCase().trim());
    if (enabled !== undefined) updateData.enabled = enabled;

    await docRef.update(updateData);

    // Audit Log
    await db.collection("audit_logs").add({
      actor_email: session.user.email,
      action: "UPDATE",
      target_slack_user_id: params.slackUserId,
      before: oldDoc.data(),
      after: { ...oldDoc.data(), ...updateData },
      created_at: FieldValue.serverTimestamp(),
    });

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Error updating routing rule:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}

export async function DELETE(req: NextRequest, { params }: { params: { slackUserId: string } }) {
  const db = getDb();
  const session = await getServerSession();
  if (!session || !session.user?.email) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  try {
    const docRef = db.collection("routing_rules").doc(params.slackUserId);
    const oldDoc = await docRef.get();
    if (!oldDoc.exists) return NextResponse.json({ error: "Not Found" }, { status: 404 });

    await docRef.delete();

    // Audit Log
    await db.collection("audit_logs").add({
      actor_email: session.user.email,
      action: "DELETE",
      target_slack_user_id: params.slackUserId,
      before: oldDoc.data(),
      created_at: FieldValue.serverTimestamp(),
    });

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Error deleting routing rule:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}
