import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#f6f8fb",   // page background (off-white)
        surface: "#ffffff",  // cards
        ink: "#0f172a",      // near-black text
        sub: "#64748b",      // muted slate
        line: "#e6e9ef",     // borders
        brand: "#2563eb",    // primary blue
        up: "#16a34a",       // long / win
        down: "#dc2626",     // short / loss
        warn: "#d97706",     // warming
      },
      boxShadow: {
        card: "0 1px 2px rgba(16,24,40,.04), 0 1px 3px rgba(16,24,40,.06)",
        pop: "0 4px 16px rgba(16,24,40,.08)",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "Segoe UI", "Arial"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};
export default config;
