import type { Metadata } from "next";
import { Fraunces, Inter, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-fraunces",
  weight: ["500", "600", "700"],
});
const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  variable: "--font-plex-mono",
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "pmupredict — Le programme augmenté",
  description: "Pronostics hippiques fusionnant IA, presse et communauté.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body className={`${fraunces.variable} ${inter.variable} ${plexMono.variable} paper-texture`}>
        <header className="border-b border-paper-line bg-turf text-paper">
          <div className="mx-auto max-w-4xl px-6 py-5 flex flex-col gap-3 sm:flex-row sm:items-baseline sm:justify-between">
            <a href="/" className="font-display text-2xl tracking-tight">
              pmupredict
            </a>
            <nav className="flex gap-6 font-body text-sm uppercase tracking-wide">
              <a href="/" className="hover:text-gold transition-colors">
                Programme du jour
              </a>
              <a href="/tipsters" className="hover:text-gold transition-colors">
                Tipsters
              </a>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-4xl px-6 py-10">{children}</main>
      </body>
    </html>
  );
}
