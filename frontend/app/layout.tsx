import type { Metadata, Viewport } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { ToastProvider } from "@/components/ui/Toast";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Health AI · CBC Analyzer",
    template: "%s · Health AI",
  },
  description:
    "AI-powered Complete Blood Count analyzer. Upload any CBC report and get instant risk scoring, clinical synthesis, and an AI chatbot to answer your questions.",
  keywords: ["CBC", "blood test", "AI health", "complete blood count", "clinical analysis"],
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#09090b",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <ClerkProvider
      signInUrl="/sign-in"
      signUpUrl="/sign-up"
      signInFallbackRedirectUrl="/dashboard"
      signUpFallbackRedirectUrl="/dashboard"
      afterSignOutUrl="/"
    >
      <html lang="en" className="scroll-smooth">
        <body suppressHydrationWarning>
          <ToastProvider>{children}</ToastProvider>
        </body>
      </html>
    </ClerkProvider>
  );
}
