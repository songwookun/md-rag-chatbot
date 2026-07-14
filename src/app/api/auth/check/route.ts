import { NextRequest, NextResponse } from "next/server";
import { verifyAuthToken } from "@/lib/auth";

// 현재 인증 상태 확인
export async function GET(req: NextRequest) {
  if (verifyAuthToken(req)) {
    return NextResponse.json({ authenticated: true });
  }
  return NextResponse.json({ authenticated: false }, { status: 401 });
}
