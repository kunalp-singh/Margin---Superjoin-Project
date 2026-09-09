import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Margin — Fact Knowledge Layer",
  description: "Grounding PDF claims, cross-document corroboration, contradiction detection, and contextual reconciliation.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="bg-paper-bg text-paper-ink antialiased min-h-screen">
        {children}
      </body>
    </html>
  );
}

