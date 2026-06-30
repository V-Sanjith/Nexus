import type { Metadata } from "next";
import { GlobalProviders } from "@/providers";
import "@/app/globals.css";

export const metadata: Metadata = {
  title: "Nexus — Every decision. Smarter.",
  description: "AI-powered decision engine for structured requirement mapping and specification audits.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="font-sans antialiased bg-background text-foreground">
        <GlobalProviders>{children}</GlobalProviders>
      </body>
    </html>
  );
}
