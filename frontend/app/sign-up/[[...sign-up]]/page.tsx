import { SignUp } from "@clerk/nextjs";
import { HeartPulse, BarChart2, MessageSquare, Sparkles } from "lucide-react";

export default function SignUpPage() {
  return (
    <div className="min-h-screen bg-background flex overflow-hidden relative">

      {/* ── Medical grid + ambient ── */}
      <div className="absolute inset-0 pointer-events-none" aria-hidden="true">
        <div className="absolute inset-0 medical-grid opacity-50" />
        <div className="absolute top-[-20%] right-[-8%] w-[700px] h-[700px] rounded-full glow-orb"
          style={{ background: "radial-gradient(circle, rgba(0,119,182,0.14) 0%, transparent 70%)" }} />
        <div className="absolute bottom-[-15%] left-[-5%] w-[600px] h-[600px] rounded-full glow-orb glow-orb-2"
          style={{ background: "radial-gradient(circle, rgba(0,180,216,0.1) 0%, transparent 70%)" }} />
        {[
          { w: 40, h: 40, top: "20%", left: "92%", dur: "9s",  del: "0s" },
          { w: 56, h: 56, top: "65%", left: "88%", dur: "12s", del: "1.5s" },
          { w: 30, h: 30, top: "30%", left: "8%",  dur: "10s", del: "0.5s" },
          { w: 48, h: 48, top: "75%", left: "12%", dur: "11s", del: "2s" },
        ].map((p, i) => (
          <div
            key={i}
            className="absolute rounded-full border border-primary/15 bg-primary/5"
            style={{ width: p.w, height: p.h, top: p.top, left: p.left,
              animation: `cellFloat ${p.dur} ease-in-out infinite ${p.del}` }}
          />
        ))}
      </div>

      {/* ── Left: Clerk sign-up form ── */}
      <div className="flex-1 flex items-center justify-center p-6 lg:p-12 relative z-10">
        {/* Mobile logo */}
        <div className="absolute top-6 left-6 flex items-center gap-2 lg:hidden">
          <div className="p-1.5 bg-primary/15 rounded-xl border border-primary/20">
            <HeartPulse className="w-4 h-4 text-primary" />
          </div>
          <span className="font-display font-bold text-slate-900 text-sm">Health AI</span>
        </div>

        <SignUp
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

      {/* ── Right brand panel (desktop only) ── */}
      <div className="hidden lg:flex lg:w-[52%] relative flex-col justify-between p-16 border-l border-white/5">
        {/* Logo */}
        <div className="flex items-center gap-3 justify-end">
          <div>
            <span className="font-display font-bold text-slate-900 text-lg block leading-tight text-right">Health AI</span>
            <span className="text-[11px] text-primary/60 font-mono block text-right">CBC Analyzer</span>
          </div>
          <div className="p-2.5 bg-primary/15 rounded-2xl border border-primary/20">
            <HeartPulse className="w-6 h-6 text-primary" />
          </div>
        </div>

        {/* Hero text */}
        <div className="space-y-8 animate-slide-up">
          <div>
            <h1 className="text-5xl font-display font-bold text-slate-900 leading-tight mb-4">
              Your health data,<br />
              <span style={{
                background: "linear-gradient(135deg, #90e0ef, #00b4d8, #0077b6)",
                WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", backgroundClip: "text",
              }}>
                clearly explained
              </span>
            </h1>
            <p className="text-zinc-400 text-lg leading-relaxed max-w-md">
              Join thousands who use Health AI to make sense of their blood work
              with clinical-grade AI analysis.
            </p>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 gap-4">
            {[
              { value: "30+", label: "CBC parameters", color: "text-primary" },
              { value: "98%", label: "Extraction accuracy", color: "text-accent" },
              { value: "5min", label: "Full analysis", color: "text-primaryGlow" },
              { value: "12+", label: "Lab formats", color: "text-primary" },
            ].map((s) => (
              <div key={s.label} className="p-4 rounded-2xl bg-surface/40 border border-white/5">
                <div className={`text-2xl font-display font-bold ${s.color} mb-0.5`}>{s.value}</div>
                <div className="text-xs text-zinc-500">{s.label}</div>
              </div>
            ))}
          </div>
        </div>

        <p className="text-xs text-zinc-700 font-mono text-right">
          Not a substitute for professional medical advice.
        </p>
      </div>
    </div>
  );
}
