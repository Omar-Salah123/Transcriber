import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "فاتورتي | مراجعة الفواتير",
  description: "واجهة مراجعة الفواتير قبل تصديرها إلى Excel.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ar" dir="rtl">
      <body>{children}</body>
    </html>
  );
}
