import { auth } from "@clerk/nextjs/server";
import { NextRequest } from "next/server";
import { supabase } from "@/lib/supabase";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { userId } = await auth();
  if (!userId) return new Response("Unauthorized", { status: 401 });

  const { id } = await params;

  const { data, error } = await supabase
    .from("reports")
    .select("id, filename, title, risk_score, rag_collection_name, created_at, analysis_data")
    .eq("id", id)
    .eq("user_id", userId)
    .single();

  if (error || !data) {
    return Response.json({ error: "Not found" }, { status: 404 });
  }

  return Response.json({
    id: data.id,
    filename: data.filename,
    title: data.title,
    risk_score: data.risk_score,
    rag_collection_name: data.rag_collection_name,
    created_at: data.created_at,
    ...data.analysis_data,
  });
}

export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { userId } = await auth();
  if (!userId) return new Response("Unauthorized", { status: 401 });

  const { id } = await params;

  const { error } = await supabase
    .from("reports")
    .delete()
    .eq("id", id)
    .eq("user_id", userId);

  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }

  return new Response(null, { status: 204 });
}
