import { auth } from "@clerk/nextjs/server";
import { NextRequest } from "next/server";
import { supabaseServer as supabase } from "@/lib/supabase";

export async function POST(req: NextRequest) {
  const { userId } = await auth();
  if (!userId) return new Response("Unauthorized", { status: 401 });

  const body = await req.json();
  const { question, collection_name, session_id, report_id, messages } = body;

  const FASTAPI_URL = process.env.FASTAPI_URL;
  if (!FASTAPI_URL) {
    return Response.json({ error: "Backend URL not configured. Set FASTAPI_URL in environment variables." }, { status: 503 });
  }

  let res: Response;
  try {
    res = await fetch(`${FASTAPI_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, collection_name, session_id }),
    });
  } catch (err: unknown) {
    const isAbort = err instanceof Error && err.name === "AbortError";
    return Response.json(
      { error: isAbort ? "Request timed out." : "Failed to reach analysis server. Check backend is running." },
      { status: isAbort ? 504 : 502 }
    );
  }

  if (!res.ok) {
    return Response.json({ error: "Failed to generate answer" }, { status: res.status });
  }

  const data = await res.json();
  const answer = data.answer;

  // Save to DB if report_id and messages are provided
  if (report_id && messages) {
    const updatedMessages = [
      ...messages,
      { role: "user", content: question },
      { role: "assistant", content: answer }
    ];

    // Fetch the current analysis_data to preserve it
    const { data: reportRecord } = await supabase
      .from("reports")
      .select("analysis_data")
      .eq("id", report_id)
      .eq("user_id", userId)
      .single();

    if (reportRecord) {
      const newAnalysisData = {
        ...reportRecord.analysis_data,
        chat_history: updatedMessages
      };

      await supabase
        .from("reports")
        .update({ analysis_data: newAnalysisData })
        .eq("id", report_id)
        .eq("user_id", userId);
    }
  }

  return Response.json(data, { status: res.status });
}
