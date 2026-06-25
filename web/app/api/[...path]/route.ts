import { NextRequest, NextResponse } from "next/server";

/** Runtime backend URL — auto-detects Railway; override with API_URL env var. */
function backend(): string {
  if (process.env.API_URL) return process.env.API_URL.replace(/\/$/, "");
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL.replace(/\/$/, "");
  if (process.env.RAILWAY_ENVIRONMENT) {
    return "https://web-production-6447a.up.railway.app";
  }
  return "http://localhost:8000";
}

async function proxy(req: NextRequest, path: string[]) {
  const tail = path.join("/");
  const url = `${backend()}/api/${tail}${req.nextUrl.search}`;
  const init: RequestInit = {
    method: req.method,
    cache: "no-store",
    headers: { Accept: req.headers.get("accept") || "*/*" },
  };
  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = await req.arrayBuffer();
  }
  const res = await fetch(url, init);
  const ct = res.headers.get("content-type") || "application/json";
  if (ct.includes("image") || ct.includes("octet-stream")) {
    return new NextResponse(await res.arrayBuffer(), {
      status: res.status,
      headers: { "Content-Type": ct, "Cache-Control": "no-store" },
    });
  }
  const text = await res.text();
  return new NextResponse(text, {
    status: res.status,
    headers: { "Content-Type": ct, "Cache-Control": "no-store" },
  });
}

export async function GET(req: NextRequest, ctx: { params: { path: string[] } }) {
  return proxy(req, ctx.params.path);
}

export async function POST(req: NextRequest, ctx: { params: { path: string[] } }) {
  return proxy(req, ctx.params.path);
}

export async function OPTIONS() {
  return new NextResponse(null, { status: 204 });
}
