import { SignUp } from "@clerk/nextjs";
import { HeartPulse, BarChart2, MessageSquare, Sparkles } from "lucide-react";

export default function SignUpPage() {
  return (
    <div className="min-h-screen bg-background flex overflow-hidden relative">

      {/* ── Medical grid + ambient ── */}
      <div className="absolute inset-0 pointer-events-none" aria-hidden="true">
        <div className="absolute inset-0 medical-grid opacity-50" />
        <div className="absolute top-[-20%] right-[-8%] w-[700px] h-[700px] rounded-full glow-orb"
          style={{ background: "radial-gradient(circle, rgba(14,165,233,0.12) 0%, transparent 70%)" }} />
        <div className="absolute bottom-[-15%] left-[-5%] w-[600px] h-[600px] rounded-full glow-orb glow-orb-2"
          style={{ background: "radial-gradient(circle, rgba(6,214,160,0.08) 0%, transparent 70%)" }} />
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
          <span className="font-display font-bold text-white text-sm">Health AI</span>
        </div>

        <SignUp
          appearance={{
            variables: {
              colorPrimary: "#0EA5E9",
              colorBackground: "#0f1623",
              colorText: "#f1f5f9",
              colorTextSecondary: "#94a3b8",
              colorInputBackground: "#0a1020",
              colorInputText: "#f1f5f9",
              colorNeutral: "#475569",
              borderRadius: "0.875rem",
              fontFamily: "Plus Jakarta Sans, ui-sans-serif, system-ui, sans-serif",
              fontSize: "0.9rem",
            },
            elements: {
              rootBox: "w-full max-w-md",
              card: "!bg-[#0f1623]/90 !backdrop-blur-2xl !border !border-white/8 !shadow-[0_32px_64px_rgba(0,0,0,0.6),0_0_0_1px_rgba(14,165,233,0.06)] !rounded-3xl",
              headerTitle: "!text-white !font-display !tracking-tight",
              headerSubtitle: "!text-slate-400",
              socialButtonsBlockButton: "!bg-white/[0.04] !border !border-white/10 !text-white hover:!bg-white/[0.08] !rounded-xl !transition-all",
              socialButtonsBlockButtonText: "!text-white !font-medium",
              dividerLine: "!bg-white/8",
              dividerText: "!text-slate-500 !text-xs",
              formFieldLabel: "!text-slate-400 !text-xs !font-medium !tracking-wide",
              formFieldInput: "!bg-[#0a1020] !border !border-white/10 !text-white !rounded-xl focus:!border-sky-500/50 focus:!ring-1 focus:!ring-sky-500/30 !transition-all",
              formButtonPrimary: "!bg-gradient-to-r !from-sky-500 !to-sky-600 !text-white !font-semibold !rounded-xl !shadow-[0_4px_20px_rgba(14,165,233,0.3)] hover:!shadow-[0_8px_28px_rgba(14,165,233,0.45)] hover:!brightness-110 !transition-all",
              footerActionText: "!text-slate-500",
              footerActionLink: "!text-sky-400 hover:!text-sky-300 !font-medium",
              identityPreviewText: "!text-white",
              identityPreviewEditButton: "!text-sky-400",
              formFieldSuccessText: "!text-emerald-400",
              formFieldErrorText: "!text-red-400",
              alertText: "!text-red-400",
              otpCodeFieldInput: "!bg-[#0a1020] !border !border-white/10 !text-white !rounded-xl",
            },
          }}
        />
      </div>

      {/* ── Right brand panel (desktop only) ── */}
      <div className="hidden lg:flex lg:w-[52%] relative flex-col justify-between p-16 border-l border-white/5">
        {/* Logo */}
        <div className="flex items-center gap-3 justify-end">
          <div>
            <span className="font-display font-bold text-white text-lg block leading-tight text-right">Health AI</span>
            <span className="text-[11px] text-primary/60 font-mono block text-right">CBC Analyzer</span>
          </div>
          <div className="p-2.5 bg-primary/15 rounded-2xl border border-primary/20">
            <HeartPulse className="w-6 h-6 text-primary" />
          </div>
        </div>

        {/* Hero text */}
        <div className="space-y-8 animate-slide-up">
          <div>
            <h1 className="text-5xl font-display font-bold text-white leading-tight mb-4">
              Your health data,<br />
              <span style={{
                background: "linear-gradient(135deg, #06D6A0, #0EA5E9)",
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
              { value: "5min", label: "Full analysis", color: "text-violet-400" },
              { value: "12+", label: "Lab formats", color: "text-sky-300" },
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
