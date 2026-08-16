import type { Metadata } from "next";
import { Noto_Sans_KR } from "next/font/google";

import "./globals.css";

const notoSansKR = Noto_Sans_KR({
  subsets: ["latin"],
  weight: ["300", "400", "500", "700"],
  variable: "--font-sans",
});

export const metadata: Metadata = {
  title: "큐닷 카드뉴스",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" className={notoSansKR.variable}>
      <body>{children}</body>
    </html>
  );
}
