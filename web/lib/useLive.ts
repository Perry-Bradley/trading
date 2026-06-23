"use client";
import { useEffect } from "react";

/** Run `fn` now, on an interval, and whenever a tick completes (msnr:refresh). */
export function useLive(fn: () => void, ms = 15000) {
  useEffect(() => {
    fn();
    const t = setInterval(fn, ms);
    const h = () => fn();
    window.addEventListener("msnr:refresh", h);
    return () => {
      clearInterval(t);
      window.removeEventListener("msnr:refresh", h);
    };
  }, [fn, ms]);
}

export function fmtPrice(v: number) {
  if (!isFinite(v) || v === 0) return "—";
  if (Math.abs(v) >= 1000) return v.toFixed(1);
  if (Math.abs(v) >= 100) return v.toFixed(3);
  return v.toFixed(5);
}
