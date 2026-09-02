import { NextRequest } from "next/server";
import { proxy } from "@/lib/proxy";

// 외부 수집(iOS 단축어 등) — 쿠키가 아니라 Authorization 헤더로 인증한다
export async function POST(req: NextRequest) {
  return proxy(req, "/api/collect");
}
