import type { Metadata, Viewport } from "next";
import "./globals.css";
import Shell from "@/components/Shell";

export const metadata: Metadata = {
  title: "MSNR Trading Assistant",
  description: "Malaysian SNR + Smart Money signals — self-learning paper-trading SaaS",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#f6f8fb",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="font-sans antialiased text-ink">
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
