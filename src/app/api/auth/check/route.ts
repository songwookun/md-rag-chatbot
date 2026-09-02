import { NextRequest } from "next/server";
import { proxy } from "@/lib/proxy";

// ★ 절대 캐시되면 안 된다. 캐시되면 모든 방문자가 첫 응답(인증됨/아님)을 공유한다.
export const dynamic = "force-dynamic";

// 인증 상태 확인 — 미인증이면 백엔드가 401 을 주고, page.tsx 가 res.ok 로 판정한다
export async function GET(req: NextRequest) {
  return proxy(req, "/api/auth/check");
}
