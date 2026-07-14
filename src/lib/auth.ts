import { NextRequest, NextResponse } from "next/server";
import { createHmac, timingSafeEqual } from "crypto";

const TOKEN_COOKIE = "auth_token";
const TOKEN_MAX_AGE = 60 * 60 * 24; // 24시간(초)

// 서명키: 별도 시크릿 있으면 그걸, 없으면 로그인 비번 재사용
function getSecret(): string {
  const s = process.env.AUTH_SECRET || process.env.AUTH_PASSWORD;
  if (!s) throw new Error("AUTH secret not configured");
  return s;
}

// payload를 HMAC-SHA256으로 서명 (서버 상태 없이 검증하려고)
function sign(payload: string): string {
  return createHmac("sha256", getSecret()).update(payload).digest("hex");
}

// 새 토큰 발급 = "만료시각.서명" — 서버에 저장 안 함(무상태)
export function createAuthToken(): { token: string; cookie: string } {
  const payload = String(Date.now() + TOKEN_MAX_AGE * 1000); // 만료 시각(ms)
  const token = `${payload}.${sign(payload)}`;

  // Secure는 HTTPS 전용 → 로컬 http 테스트에서 쿠키 거부되지 않게 프로덕션만
  const secure = process.env.NODE_ENV === "production" ? "; Secure" : "";
  const cookie = `${TOKEN_COOKIE}=${token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${TOKEN_MAX_AGE}${secure}`;
  return { token, cookie };
}

// 토큰 검증 = 서명 재계산 비교 + 만료 확인 (서버 상태 조회 없음)
export function verifyAuthToken(req: NextRequest): boolean {
  const raw = req.cookies.get(TOKEN_COOKIE)?.value;
  if (!raw) return false;

  const dot = raw.lastIndexOf(".");
  if (dot < 0) return false;
  const payload = raw.slice(0, dot);
  const sig = raw.slice(dot + 1);

  // 서명 위조 방지 (타이밍 세이프 비교)
  const a = Buffer.from(sig);
  const b = Buffer.from(sign(payload));
  if (a.length !== b.length || !timingSafeEqual(a, b)) return false;

  // 만료 확인
  const exp = Number(payload);
  if (!Number.isFinite(exp) || exp < Date.now()) return false;

  return true;
}

// 인증 실패 응답
export function unauthorizedResponse(): NextResponse {
  return NextResponse.json(
    { reply: "⚠️ 인증이 필요합니다. 다시 로그인해주세요." },
    { status: 401 }
  );
}
