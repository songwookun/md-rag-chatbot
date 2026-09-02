import { NextRequest } from "next/server";
import { proxy } from "@/lib/proxy";

// 로그인 — 백엔드가 발급한 HttpOnly 쿠키를 그대로 브라우저에 전달한다
export async function POST(req: NextRequest) {
  return proxy(req, "/api/auth");
}
