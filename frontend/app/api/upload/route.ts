import { auth } from "@clerk/nextjs/server";
import { NextRequest } from "next/server";
import { supabase } from "@/lib/supabase";

// Allow up to 5 minutes for OCR-heavy PDFs (Vercel/Next.js max)
export const maxDuration = 300;

export async function POST(req: NextRequest) {
  const { userId } = await auth();
  if (!userId) return new Response("Unauthorized", { status: 401 });

  const formData = await req.formData();
  const file = formData.get("file") as File | null;

  const FASTAPI_URL = process.env.FASTAPI_URL || "http://localhost:8000";
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 290_000); // 290s — just under backend 300s

  let res: Response;
  try {
    res = await fetch(`${FASTAPI_URL}/analyze`, {
      method: "POST",
      body: formData,
      signal: controller.signal,
    });
  } catch (err: unknown) {
    clearTimeout(timeoutId);
    const isAbort = err instanceof Error && err.name === "AbortError";
    return Response.json(
      { detail: isAbort ? "Analysis timed out. Please try again with a smaller file." : "Failed to reach analysis server." },
      { status: isAbort ? 504 : 502 }
    );
  } finally {
    clearTimeout(timeoutId);
  }

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
