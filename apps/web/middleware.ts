import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_EXACT = new Set([
  "/",
  "/login",
  "/signup",
  "/forgot-password",
  "/reset-password",
  "/architecture",
]);

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (PUBLIC_EXACT.has(pathname)) {
    return NextResponse.next();
  }
  const session = request.cookies.get("payintel_session")?.value;
  if (!session) {
    const login = request.nextUrl.clone();
    login.pathname = "/login";
    login.search = `?next=${encodeURIComponent(`${pathname}${request.nextUrl.search}`)}`;
    return NextResponse.redirect(login);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|backend|health).*)"],
};
