import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "@/contexts/ThemeContext";
import { WalkthroughProvider } from "@/contexts/WalkthroughContext";

export const metadata: Metadata = {
  title: "Yoke Agent — AI Quality Studio",
  description: "Mistake-proof your AI — optimize RAG pipelines and evaluate AI agents",
  icons: {
    icon: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" data-theme="neon" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var theme = localStorage.getItem('rag-theme');
                  if (theme && ['light','dark','neon'].includes(theme)) {
                    document.documentElement.setAttribute('data-theme', theme);
                  }
                } catch(e) {}
              })();
            `,
          }}
        />
      </head>
      <body className="antialiased min-h-screen bg-surface">
        <ThemeProvider>
          <WalkthroughProvider>{children}</WalkthroughProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
