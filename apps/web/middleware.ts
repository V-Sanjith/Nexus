import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const token = request.cookies.get("session_token")?.value;
  const path = request.nextUrl.pathname;

  // Protect all application paths
  const isProtectedPath = path.startsWith("/home") || 
                          path.startsWith("/decide") || 
                          path.startsWith("/decisions") || 
                          path.startsWith("/timeline") ||
                          path.startsWith("/dna") ||
                          path.startsWith("/memory") ||
                          path.startsWith("/insights") ||
                          path.startsWith("/graph") ||
                          path.startsWith("/settings");

  if (isProtectedPath && !token) {
    const loginUrl = new URL("/", request.url);
    return NextResponse.redirect(loginUrl);
  }

  // Inject correlation request ID headers for request tracing
  const response = NextResponse.next();
  const requestId = request.headers.get("x-request-id") || crypto.randomUUID();
  response.headers.set("x-request-id", requestId);
  
  return response;
}

export const config = {
  matcher: [
    "/((?!api|_next/static|_next/image|favicon.ico|share|fonts|images).*)",
  ],
};
