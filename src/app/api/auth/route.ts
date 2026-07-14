import { NextRequest, NextResponse } from "next/server";
import { createAuthToken } from "@/lib/auth";

export async function POST(req: NextRequest) {
  const { password } = await req.json();

  if (password !== process.env.AUTH_PASSWORD) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { cookie } = createAuthToken();

  const res = NextResponse.json({ success: true });
  res.headers.set("Set-Cookie", cookie);
  return res;
}
