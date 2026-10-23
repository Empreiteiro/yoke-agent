import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "@/contexts/ThemeContext";
import { ACCENTS, THEMES, ACCENT_STORAGE_KEY, THEME_STORAGE_KEY } from "@/lib/theme";
import { WalkthroughProvider } from "@/contexts/WalkthroughContext";
import { AuthProvider } from "@/contexts/AuthContext";
import AuthGate from "@/components/AuthGate";

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
    <html lang="en" data-theme="neon" data-accent="violet" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500&family=Inter:wght@300;400;500;600;700&display=swap"
        />
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var theme = localStorage.getItem('${THEME_STORAGE_KEY}');
                  if (theme && ${JSON.stringify(THEMES)}.includes(theme)) {
                    document.documentElement.setAttribute('data-theme', theme);
                  }
                  var accent = localStorage.getItem('${ACCENT_STORAGE_KEY}');
                  if (accent && ${JSON.stringify(ACCENTS)}.includes(accent)) {
                    document.documentElement.setAttribute('data-accent', accent);
                  }
                } catch(e) {}
              })();
            `,
          }}
        />
      </head>
      <body className="antialiased min-h-screen bg-surface">
        <ThemeProvider>
          <AuthProvider>
            <AuthGate>
              <WalkthroughProvider>{children}</WalkthroughProvider>
            </AuthGate>
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
