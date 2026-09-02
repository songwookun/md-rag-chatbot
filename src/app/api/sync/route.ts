import { NextRequest } from "next/server";
import { proxy } from "@/lib/proxy";

// 전체 재색인
export async function POST(req: NextRequest) {
  return proxy(req, "/api/sync");
}
