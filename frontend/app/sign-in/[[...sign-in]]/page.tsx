import { SignIn } from "@clerk/nextjs";
import { HeartPulse, Activity, ShieldCheck, Microscope } from "lucide-react";

export default function SignInPage() {
  return (
    <div className="min-h-screen bg-background flex overflow-hidden relative">

      {/* ── Medical grid + ambient ── */}
      <div className="absolute inset-0 pointer-events-none" aria-hidden="true">
        <div className="absolute inset-0 medical-grid opacity-50" />
        <div className="absolute top-[-20%] left-[-10%] w-[700px] h-[700px] rounded-full glow-orb"
          style={{ background: "radial-gradient(circle, rgba(0,119,182,0.16) 0%, transparent 70%)" }} />
        <div className="absolute bottom-[-15%] right-[-5%] w-[600px] h-[600px] rounded-full glow-orb glow-orb-2"
          style={{ background: "radial-gradient(circle, rgba(0,180,216,0.1) 0%, transparent 70%)" }} />
        {/* Floating cells */}
        {[
          { w: 48, h: 48, top: "15%", left: "10%", dur: "9s", del: "0s" },
          { w: 32, h: 32, top: "70%", left: "6%",  dur: "11s", del: "2s" },
          { w: 56, h: 56, top: "40%", left: "88%", dur: "10s", del: "1s" },
          { w: 24, h: 24, top: "80%", left: "85%", dur: "8s",  del: "3s" },
        ].map((p, i) => (
          <div
            key={i}
            className="absolute rounded-full border border-primary/15 bg-primary/5"
            style={{ width: p.w, height: p.h, top: p.top, left: p.left,
              animation: `cellFloat ${p.dur} ease-in-out infinite ${p.del}` }}
          />
        ))}
      </div>

      {/* ── Left brand panel (desktop only) ── */}
      <div className="hidden lg:flex lg:w-[52%] relative flex-col justify-between p-16 border-r border-white/5">
        {/* Logo */}
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-primary/15 rounded-2xl border border-primary/20">
            <HeartPulse className="w-6 h-6 text-primary" />
          </div>
          <div>
            <span className="font-display font-bold text-slate-900 text-lg block leading-tight">Health AI</span>
            <span className="text-[11px] text-primary/60 font-mono">CBC Analyzer</span>
          </div>
        </div>

        {/* Hero text */}
        <div className="space-y-8 animate-slide-up">
          <div>
            <h1 className="text-5xl font-display font-bold text-slate-900 leading-tight mb-4">
              Clinical insights<br />
              <span style={{
                background: "linear-gradient(135deg, #90e0ef, #00b4d8, #0077b6)",
                WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", backgroundClip: "text",
              }}>
                powered by AI
              </span>
            </h1>
            <p className="text-zinc-400 text-lg leading-relaxed max-w-md">
              Upload any CBC report and get instant risk scoring, clinical synthesis,
              and an AI chatbot grounded in your data.
            </p>
          </div>

          {/* Feature pills */}
          <div className="flex flex-col gap-3">
            {[
              { icon: <Activity className="w-4 h-4" />, text: "AI-powered parameter extraction" },
              { icon: <ShieldCheck className="w-4 h-4" />, text: "Risk scoring with clinical rationale" },
              { icon: <Microscope className="w-4 h-4" />, text: "RAG chatbot grounded in your report" },
            ].map((f) => (
              <div key={f.text} className="flex items-center gap-3 text-sm text-zinc-400">
                <div className="p-1.5 rounded-lg bg-primary/10 text-primary border border-primary/15">
                  {f.icon}
                </div>
                {f.text}
              </div>
            ))}
          </div>
        </div>

        {/* Bottom tagline */}
        <p className="text-xs text-zinc-700 font-mono">
          Not a substitute for professional medical advice.
        </p>
      </div>

      {/* ── Right: Clerk sign-in form ── */}
      <div className="flex-1 flex items-center justify-center p-6 lg:p-12 relative z-10">
        {/* Mobile logo */}
        <div className="absolute top-6 left-6 flex items-center gap-2 lg:hidden">
          <div className="p-1.5 bg-primary/15 rounded-xl border border-primary/20">
            <HeartPulse className="w-4 h-4 text-primary" />
          </div>
          <span className="font-display font-bold text-slate-900 text-sm">Health AI</span>
        </div>

        <SignIn
          appearance={{
            variables: {
              colorPrimary: "#0077B6",
              colorBackground: "#ffffff",
              colorText: "#0f172a",
              colorTextSecondary: "#64748b",
              colorInputBackground: "#f8fafc",
              colorInputText: "#0f172a",
              colorNeutral: "#cbd5e1",
              borderRadius: "0.875rem",
              fontFamily: "Plus Jakarta Sans, ui-sans-serif, system-ui, sans-serif",
              fontSize: "0.9rem",
            },
            elements: {
              rootBox: "w-full max-w-md",
              card: "!bg-white/95 !backdrop-blur-2xl !border !border-slate-200 !shadow-[0_24px_60px_rgba(0,119,182,0.12),0_0_0_1px_rgba(0,180,216,0.08)] !rounded-3xl",
              headerTitle: "!text-slate-900 !font-display !tracking-tight",
              headerSubtitle: "!text-slate-500",
              socialButtonsBlockButton: "!bg-slate-50 !border !border-slate-200 !text-slate-900 hover:!bg-slate-100 !rounded-xl !transition-all",
              socialButtonsBlockButtonText: "!text-slate-900 !font-medium",
              dividerLine: "!bg-slate-200",
              dividerText: "!text-slate-400 !text-xs",
              formFieldLabel: "!text-slate-500 !text-xs !font-medium !tracking-wide",
              formFieldAction: "!hidden",
              formFieldInput: "!bg-slate-50 !border !border-slate-200 !text-slate-900 !rounded-xl focus:!border-[#0077B6]/50 focus:!ring-1 focus:!ring-[#00B4D8]/20 !transition-all",
              formButtonPrimary: "!bg-gradient-to-r !from-[#00B4D8] !to-[#0077B6] !text-white !font-semibold !rounded-xl !shadow-[0_4px_20px_rgba(0,119,182,0.25)] hover:!shadow-[0_8px_28px_rgba(0,119,182,0.35)] hover:!brightness-110 !transition-all",
              footerActionText: "!text-slate-500",
              footerActionLink: "!text-[#0077B6] hover:!text-[#03045E] !font-medium",
              identityPreviewText: "!text-slate-900",
              identityPreviewEditButton: "!text-[#00B4D8]",
              formFieldSuccessText: "!text-emerald-400",
              formFieldErrorText: "!text-red-400",
              alertText: "!text-red-400",
              otpCodeFieldInput: "!bg-slate-50 !border !border-slate-200 !text-slate-900 !rounded-xl",
              footer: "!bg-transparent [&>div]:!bg-transparent",
              badge: "!hidden",
            },
          }}
        />
      </div>
    </div>
  );
}
