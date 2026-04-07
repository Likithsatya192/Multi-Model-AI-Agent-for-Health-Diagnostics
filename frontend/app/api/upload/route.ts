import { auth } from "@clerk/nextjs/server";
import { NextRequest } from "next/server";

export async function POST(req: NextRequest) {
  const { userId } = await auth();
  if (!userId) return new Response("Unauthorized", { status: 401 });

  const formData = await req.formData();

  const FASTAPI_URL = process.env.FASTAPI_URL || "http://localhost:8000";
  const res = await fetch(`${FASTAPI_URL}/analyze`, {
    method: "POST",
    body: formData,
  });

  const data = await res.json();
  return Response.json(data, { status: res.status });
}
