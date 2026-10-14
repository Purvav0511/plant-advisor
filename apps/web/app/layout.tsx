import type { Metadata } from "next";
import "./globals.css";

// Fonts and theme tokens come from the Figma designs (decision 0016, PLAN 5.1).
export const metadata: Metadata = {
  title: "Plant Advisor",
  description:
    "Wear diagnosis and product recommendations for plant components",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex min-h-full flex-col">{children}</body>
    </html>
  );
}
