import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "showrunner",
  description: "Multi-agent content production system",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
