import { auth } from "@clerk/nextjs/server";
import { NextRequest } from "next/server";
import { supabase } from "@/lib/supabase";

export async function POST(req: NextRequest) {
  const { userId } = await auth();
  if (!userId) return new Response("Unauthorized", { status: 401 });

  const formData = await req.formData();
  const file = formData.get("file") as File | null;

  const FASTAPI_URL = process.env.FASTAPI_URL || "http://localhost:8000";
  const res = await fetch(`${FASTAPI_URL}/analyze`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Analysis failed" }));
    return Response.json(err, { status: res.status });
  }

  const analysis = await res.json();

  let title = "CBC Report Analysis";
  if (analysis.patterns && Array.isArray(analysis.patterns) && analysis.patterns.length > 0) {
    // Join all detected patterns: "Microcytic Anemia & Leukocytosis"
    title = analysis.patterns.join(" & ");
  }

  const filename = file?.name ?? "unknown";

  const { data: record, error } = await supabase
    .from("reports")
    .insert({
      user_id: userId,
      filename,
      title,
      rag_collection_name: analysis.rag_collection_name ?? null,
      risk_score: analysis.risk_score ?? 0,
      analysis_data: analysis,
    })
    .select("id, created_at")
    .single();

  if (error) {
    console.error("Supabase insert error:", error);
    // Still return the analysis even if DB save fails
    return Response.json({ ...analysis, title, filename });
  }

  return Response.json({
    ...analysis,
    id: record.id,
    title,
    filename,
    created_at: record.created_at,
  });
}
