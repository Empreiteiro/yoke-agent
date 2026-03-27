import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RAG Optimization Pipeline",
  description: "End-to-end platform for optimizing Retrieval-Augmented Generation pipelines",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased min-h-screen bg-surface">
        {children}
      </body>
    </html>
  );
}
