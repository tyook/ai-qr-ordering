import type { Metadata } from "next";
import localFont from "next/font/local";
import Script from "next/script";
import "./globals.css";
import { ConditionalHeader } from "@/components/ConditionalHeader";
import { QueryProvider } from "@/components/QueryProvider";
import { ThemeProvider } from "@/components/ThemeProvider";
import { AppleAuthInit } from "@/components/AppleAuthInit";
import { OnboardingBanner } from "@/components/onboarding/onboarding-banner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { CookieBanner } from "@/components/CookieBanner";
import { Toaster } from "@/components/ui/toaster";
import { WebOnlyScripts } from "@/components/WebOnlyScripts";
import { NativeInitializer } from "@/components/NativeInitializer";
import { AuthInitializer } from "@/components/AuthInitializer";

const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist-sans",
  weight: "100 900",
});
const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-geist-mono",
  weight: "100 900",
});

export const metadata: Metadata = {
  title: {
    default: "MenuChat",
    template: "%s | MenuChat",
  },
  description: "AI-powered QR ordering for restaurants",
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover" as const,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <WebOnlyScripts />
        <Script
          src={`https://maps.googleapis.com/maps/api/js?key=${process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY}&libraries=places`}
          strategy="lazyOnload"
        />
        <QueryProvider>
          <ThemeProvider>
            <TooltipProvider>
              <OnboardingBanner />
              <ConditionalHeader />
              <AuthInitializer />
              <AppleAuthInit />
              <NativeInitializer />
              {children}
              <CookieBanner />
              <Toaster />
            </TooltipProvider>
          </ThemeProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
