"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { UserButton } from "@clerk/nextjs";
import {
  BrainCircuit, Upload, ShieldAlert, Sparkles, Activity, FileText,
  ChevronRight, CheckCircle, BarChart2, MessageSquare, Zap, Lock,
  Microscope, HeartPulse, FlaskConical, Stethoscope, TrendingUp, ArrowRight,
  Star, Shield,
} from "lucide-react";

// ─── ECG SVG Path Component ─────────────────────────────────────────────────────

function EcgLine({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 1200 80"
      className={`ecg-svg w-full ${className}`}
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path
        d="M0,40 L80,40 L95,40 L105,8 L115,72 L122,40 L135,40
           L230,40 L245,40 L255,8 L265,72 L272,40 L285,40
           L380,40 L395,40 L405,8 L415,72 L422,40 L435,40
           L530,40 L545,40 L555,8 L565,72 L572,40 L585,40
           L680,40 L695,40 L705,8 L715,72 L722,40 L735,40
           L830,40 L845,40 L855,8 L865,72 L872,40 L885,40
           L980,40 L995,40 L1005,8 L1015,72 L1022,40 L1035,40
           L1130,40 L1145,40 L1155,8 L1165,72 L1172,40 L1200,40"
        stroke="rgba(14,165,233,0.5)"
        strokeWidth="1.5"
        fill="none"
        style={{ strokeDasharray: 2400, strokeDashoffset: 2400, animation: 'ecgTrace 5s cubic-bezier(0.4,0,0.2,1) infinite' }}
      />
      <path
        d="M0,40 L80,40 L95,40 L105,8 L115,72 L122,40 L135,40
           L230,40 L245,40 L255,8 L265,72 L272,40 L285,40
           L380,40 L395,40 L405,8 L415,72 L422,40 L435,40
           L530,40 L545,40 L555,8 L565,72 L572,40 L585,40
           L680,40 L695,40 L705,8 L715,72 L722,40 L735,40
           L830,40 L845,40 L855,8 L865,72 L872,40 L885,40
           L980,40 L995,40 L1005,8 L1015,72 L1022,40 L1035,40
           L1130,40 L1145,40 L1155,8 L1165,72 L1172,40 L1200,40"
        stroke="rgba(14,165,233,0.15)"
        strokeWidth="4"
        fill="none"
        style={{ filter: 'blur(3px)', strokeDasharray: 2400, strokeDashoffset: 2400, animation: 'ecgTrace 5s cubic-bezier(0.4,0,0.2,1) infinite' }}
      />
    </svg>
  );
}

// ─── Floating Particle ───────────────────────────────────────────────────────────

function MedicalParticle({ style }: { style: React.CSSProperties }) {
  return (
    <div
      className="absolute rounded-full border border-primary/20 bg-primary/5"
      style={style}
      aria-hidden="true"
    />
  );
}

// ─── Animated Counter ────────────────────────────────────────────────────────────

function AnimatedStat({ value, label, suffix = "" }: { value: string; label: string; suffix?: string }) {
  const [visible, setVisible] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setVisible(true); },
      { threshold: 0.4 }
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={ref} className="text-center group">
      <div
        className={`text-4xl md:text-5xl font-display font-bold text-white mb-2 transition-all duration-700 ${
          visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
        }`}
      >
        <span className="text-primary">{value}</span>
        <span className="text-primary/60 text-2xl">{suffix}</span>
      </div>
      <p className={`text-sm text-zinc-500 font-medium tracking-wide transition-all duration-700 delay-150 ${
        visible ? "opacity-100" : "opacity-0"
      }`}>
        {label}
      </p>
    </div>
  );
}

// ─── Feature Card ────────────────────────────────────────────────────────────────

function FeatureCard({ icon, color, title, desc, delay = 0 }: {
  icon: React.ReactNode; color: string; title: string; desc: string; delay?: number
}) {
  const [visible, setVisible] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setVisible(true); },
      { threshold: 0.2 }
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className={`group relative p-6 rounded-2xl border border-white/5 bg-surface/40 backdrop-blur-sm
        hover:border-primary/20 hover:bg-surface/70 transition-all duration-300 cursor-default overflow-hidden
        ${visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"}`}
      style={{ transition: `opacity 0.6s ease ${delay}ms, transform 0.6s ease ${delay}ms, background 0.3s, border-color 0.3s` }}
    >
      {/* Hover glow */}
      <div className="absolute inset-0 bg-gradient-to-br from-primary/0 to-primary/0 group-hover:from-primary/5 group-hover:to-transparent transition-all duration-500 rounded-2xl" />
      {/* Corner accent */}
      <div className="absolute top-0 right-0 w-24 h-24 bg-gradient-to-bl opacity-0 group-hover:opacity-100 transition-opacity duration-500 rounded-bl-full" style={{ background: `radial-gradient(circle at top right, rgba(14,165,233,0.08), transparent 70%)` }} />

      <div className={`relative inline-flex p-3 rounded-xl border mb-4 ${color} group-hover:scale-110 transition-transform duration-300`}>
        {icon}
      </div>
      <h3 className="relative text-base font-display font-bold text-white mb-2 group-hover:text-primary transition-colors duration-200">{title}</h3>
      <p className="relative text-sm text-zinc-500 leading-relaxed group-hover:text-zinc-400 transition-colors duration-200">{desc}</p>
    </div>
  );
}

// ─── Static data ──────────────────────────────────────────────────────────────

const FEATURES = [
  { icon: <BrainCircuit className="w-5 h-5" />, color: "text-primary bg-primary/15 border-primary/20", title: "AI Parameter Extraction", desc: "Automatically identifies and extracts all CBC parameters from PDFs and images using multi-modal LLMs with high clinical accuracy.", delay: 0 },
  { icon: <ShieldAlert className="w-5 h-5" />, color: "text-pink-400 bg-pink-500/15 border-pink-500/20", title: "Risk Score & Rationale", desc: "Every report receives a 1–10 risk score with detailed clinical rationale explaining which parameters are abnormal and why.", delay: 80 },
  { icon: <BarChart2 className="w-5 h-5" />, color: "text-accent bg-accent/15 border-accent/20", title: "Visual CBC Charts", desc: "Interactive bar charts compare each parameter against reference ranges so you can spot abnormalities at a glance.", delay: 160 },
  { icon: <MessageSquare className="w-5 h-5" />, color: "text-violet-400 bg-violet-500/15 border-violet-500/20", title: "RAG-Powered AI Chat", desc: "Ask follow-up questions about your specific report. Answers are grounded in your data via Retrieval-Augmented Generation.", delay: 0 },
  { icon: <FileText className="w-5 h-5" />, color: "text-sky-400 bg-sky-500/15 border-sky-500/20", title: "Clinical Synthesis", desc: "A comprehensive narrative synthesising all findings, patterns, and recommendations into a single readable clinical summary.", delay: 80 },
  { icon: <Activity className="w-5 h-5" />, color: "text-orange-400 bg-orange-500/15 border-orange-500/20", title: "Pattern Detection", desc: "Automatically surfaces clinically significant patterns like anaemia, leukocytosis, or thrombocytopenia from CBC data.", delay: 160 },
];

const STEPS = [
  { step: "01", title: "Upload your report", desc: "Drop a PDF or image of any CBC / blood panel report. Supports most lab formats worldwide.", icon: <Upload className="w-5 h-5" />, color: "from-primary/20 to-sky-600/10" },
  { step: "02", title: "AI analyzes in minutes", desc: "Our pipeline extracts parameters, builds a RAG knowledge base, assesses risk, and generates clinical insights.", icon: <BrainCircuit className="w-5 h-5" />, color: "from-violet-500/20 to-violet-600/10" },
  { step: "03", title: "Review & ask questions", desc: "Explore the report dashboard, view charts, and chat with AI to understand every finding in detail.", icon: <Sparkles className="w-5 h-5" />, color: "from-accent/20 to-teal-600/10" },
];

const TRUST_POINTS = [
  { text: "No medical data stored unencrypted", icon: <Lock className="w-4 h-4" /> },
  { text: "Reports saved securely to your account only", icon: <Shield className="w-4 h-4" /> },
  { text: "AI insights are for informational purposes only", icon: <Star className="w-4 h-4" /> },
  { text: "Always consult a licensed physician for diagnosis", icon: <Stethoscope className="w-4 h-4" /> },
];

const PARTICLES = [
  { width: 48, height: 48, top: '12%', left: '8%', animationDuration: '9s', animationDelay: '0s', opacity: 0.15 },
  { width: 32, height: 32, top: '25%', left: '88%', animationDuration: '12s', animationDelay: '1s', opacity: 0.1 },
  { width: 64, height: 64, top: '60%', left: '5%', animationDuration: '10s', animationDelay: '2s', opacity: 0.12 },
  { width: 24, height: 24, top: '75%', left: '80%', animationDuration: '8s', animationDelay: '0.5s', opacity: 0.08 },
  { width: 40, height: 40, top: '45%', left: '92%', animationDuration: '11s', animationDelay: '3s', opacity: 0.1 },
  { width: 56, height: 56, top: '85%', left: '35%', animationDuration: '13s', animationDelay: '1.5s', opacity: 0.08 },
];

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function LandingPage() {
  const { isSignedIn, isLoaded } = useAuth();
  const [heroVisible, setHeroVisible] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setHeroVisible(true), 100);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className="min-h-screen bg-background text-white font-sans overflow-x-hidden">

      {/* ── Fixed ambient background ── */}
      <div className="fixed inset-0 pointer-events-none z-0" aria-hidden="true">
        {/* Medical grid */}
        <div className="absolute inset-0 medical-grid opacity-60" />
        {/* Ambient orbs */}
        <div className="glow-orb absolute top-[-20%] left-[-10%] w-[800px] h-[800px] rounded-full"
          style={{ background: 'radial-gradient(circle, rgba(14,165,233,0.12) 0%, transparent 70%)' }} />
        <div className="glow-orb glow-orb-2 absolute bottom-[-15%] right-[-8%] w-[700px] h-[700px] rounded-full"
          style={{ background: 'radial-gradient(circle, rgba(6,214,160,0.08) 0%, transparent 70%)' }} />
        <div className="glow-orb glow-orb-3 absolute top-[40%] right-[20%] w-[400px] h-[400px] rounded-full"
          style={{ background: 'radial-gradient(circle, rgba(139,92,246,0.06) 0%, transparent 70%)' }} />
        {/* Floating medical particles */}
        {PARTICLES.map((p, i) => (
          <MedicalParticle
            key={i}
            style={{
              width: p.width, height: p.height,
              top: p.top, left: p.left,
              opacity: p.opacity,
              animationDuration: p.animationDuration,
              animationDelay: p.animationDelay,
              animation: `cellFloat ${p.animationDuration} ease-in-out infinite ${p.animationDelay}`,
            }}
          />
        ))}
      </div>

      <div className="relative z-10">

        {/* ── Navbar ── */}
        <header className="border-b border-white/5 bg-background/80 backdrop-blur-2xl sticky top-0 z-40">
          {/* Scanner line under nav */}
          <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-primary/40 to-transparent" />
          <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
            {/* Logo */}
            <Link href="/" className="flex items-center gap-3 group">
              <div className="relative p-2 bg-primary/10 rounded-xl border border-primary/20 group-hover:bg-primary/20 transition-colors duration-200">
                <HeartPulse className="w-5 h-5 text-primary" />
                <div className="absolute inset-0 rounded-xl bg-primary/10 blur-sm opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
              <div className="flex flex-col">
                <span className="font-display font-bold text-white text-sm leading-tight tracking-tight">Health AI</span>
                <span className="text-[10px] text-primary/60 font-mono leading-tight">CBC Analyzer</span>
              </div>
            </Link>

            {/* Nav links */}
            <nav className="hidden md:flex items-center gap-1">
              {["Features", "How it works", "Privacy"].map((item) => (
                <a
                  key={item}
                  href={`#${item.toLowerCase().replace(/\s+/g, "-")}`}
                  className="px-4 py-2 text-sm text-zinc-500 hover:text-white transition-colors rounded-lg hover:bg-white/5"
                >
                  {item}
                </a>
              ))}
            </nav>

            {/* Auth */}
            <div className="flex items-center gap-3">
              {isLoaded && (
                isSignedIn ? (
                  <UserButton />
                ) : (
                  <>
                    <Link
                      href="/sign-in"
                      className="px-4 py-2 text-sm font-medium text-zinc-400 hover:text-white transition-colors"
                    >
                      Sign In
                    </Link>
                    <Link
                      href="/sign-up"
                      className="px-4 py-2 text-sm font-semibold bg-primary hover:bg-primaryDark text-white rounded-xl transition-all duration-200 shadow-primary-sm hover:shadow-primary-md"
                    >
                      Get Started
                    </Link>
                  </>
                )
              )}
            </div>
          </div>
        </header>

        {/* ── Hero ── */}
        <section className="relative max-w-7xl mx-auto px-6 pt-24 pb-24 overflow-hidden">

          {/* ECG line background */}
          <div className="absolute left-0 right-0" style={{ top: '55%', transform: 'translateY(-50%)' }}>
            <EcgLine className="opacity-30 h-20" />
          </div>

          {/* Scanner sweep */}
          <div className="scan-line" style={{ animationDelay: '2s' }} />

          <div className="relative text-center max-w-5xl mx-auto">
            {/* Badge */}
            <div
              className={`inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-primary/10 border border-primary/25 text-primary text-xs font-semibold mb-8 transition-all duration-700 ${heroVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}
            >
              <div className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
              AI-Powered Clinical CBC Analysis
              <Zap className="w-3 h-3" />
            </div>

            {/* Headline */}
            <h1
              className={`text-5xl md:text-6xl lg:text-7xl font-display font-bold text-white leading-[1.06] tracking-tight mb-6 transition-all duration-700 delay-100 ${heroVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-6'}`}
            >
              Understand your{" "}
              <span
                className="relative inline-block"
                style={{ background: 'linear-gradient(135deg, #38BDF8, #0EA5E9, #06D6A0)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}
              >
                blood report
              </span>
              <br />
              <span className="text-zinc-300">with AI precision</span>
            </h1>

            {/* Subtext */}
            <p
              className={`text-lg md:text-xl text-zinc-400 max-w-2xl mx-auto leading-relaxed mb-10 transition-all duration-700 delay-200 ${heroVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}
            >
              Upload any Complete Blood Count report. AI extracts every parameter,
              scores your health risk, generates a clinical synthesis, and lets
              you ask follow-up questions — all in minutes.
            </p>

            {/* CTA */}
            <div
              className={`flex items-center justify-center transition-all duration-700 delay-300 ${heroVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}
            >
              <Link
                href="/dashboard"
                className="group relative inline-flex items-center gap-3 px-10 py-4 text-white font-bold rounded-2xl text-base overflow-hidden"
                style={{ background: 'linear-gradient(135deg, #0EA5E9, #0284C7)', boxShadow: '0 0 0 3px rgba(14,165,233,0.25), 0 12px 40px rgba(14,165,233,0.45), inset 0 1px 0 rgba(255,255,255,0.2)' }}
              >
                <div className="absolute inset-0 bg-white/0 group-hover:bg-white/10 transition-colors duration-200" />
                <HeartPulse className="w-5 h-5 relative" />
                <span className="relative">Go to Dashboard</span>
                <ArrowRight className="w-5 h-5 relative group-hover:translate-x-1 transition-transform" />
              </Link>
            </div>

            {/* Trust indicators */}
            <div
              className={`mt-10 flex flex-wrap items-center justify-center gap-x-8 gap-y-2 transition-all duration-700 delay-500 ${heroVisible ? 'opacity-100' : 'opacity-0'}`}
            >
              {["HIPAA-conscious design", "No data sold", "Clinical-grade AI"].map((t) => (
                <span key={t} className="flex items-center gap-1.5 text-xs text-zinc-600">
                  <CheckCircle className="w-3.5 h-3.5 text-accent" />
                  {t}
                </span>
              ))}
            </div>
          </div>

          {/* ── Hero mock report ── */}
          <div
            className={`mt-20 max-w-3xl mx-auto transition-all duration-700 delay-700 ${heroVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}
          >
            <div
              className="rounded-3xl overflow-hidden relative"
              style={{
                background: 'linear-gradient(180deg, rgba(14,165,233,0.06) 0%, rgba(15,22,35,0.9) 100%)',
                border: '1px solid rgba(14,165,233,0.15)',
                boxShadow: '0 40px 80px rgba(0,0,0,0.6), 0 0 0 1px rgba(14,165,233,0.08)',
              }}
            >
              {/* Window bar */}
              <div className="flex items-center gap-2 px-5 py-3.5 border-b bg-black/20" style={{ borderColor: 'rgba(255,255,255,0.05)' }}>
                <div className="w-2.5 h-2.5 rounded-full bg-red-500/50" />
                <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/50" />
                <div className="w-2.5 h-2.5 rounded-full bg-green-500/50" />
                <span className="ml-3 text-xs text-zinc-500 font-mono">CBC Report · AI Analysis · Live</span>
                <div className="ml-auto flex items-center gap-1.5">
                  <div className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
                  <span className="text-[10px] text-accent font-mono">SCANNING</span>
                </div>
              </div>
              {/* Parameters */}
              <div className="p-6">
                <div className="grid grid-cols-3 md:grid-cols-6 gap-3 mb-5">
                  {[
                    { name: "WBC", val: "6.2", unit: "K/µL", status: "normal" },
                    { name: "RBC", val: "3.9", unit: "M/µL", status: "low" },
                    { name: "HGB", val: "11.2", unit: "g/dL", status: "low" },
                    { name: "HCT", val: "34.1", unit: "%", status: "low" },
                    { name: "PLT", val: "245", unit: "K/µL", status: "normal" },
                    { name: "MCV", val: "72.3", unit: "fL", status: "low" },
                  ].map((p, i) => (
                    <div
                      key={p.name}
                      className={`p-3 rounded-xl text-center transition-all duration-500 ${p.status === "low" ? "bg-yellow-500/8 border border-yellow-500/20" : "bg-white/[0.03] border border-white/5"}`}
                      style={{ animation: `dataStream 0.5s ease-out ${i * 80}ms both` }}
                    >
                      <div className="text-[10px] text-zinc-500 mb-1 font-mono">{p.name}</div>
                      <div className="text-lg font-display font-bold text-white tabular-nums">{p.val}</div>
                      <div className="text-[9px] text-zinc-600 font-mono">{p.unit}</div>
                      <div className={`w-1 h-1 rounded-full mx-auto mt-1 ${p.status === "low" ? "bg-yellow-400" : "bg-green-400"}`} />
                    </div>
                  ))}
                </div>
                <div
                  className="flex items-center justify-between p-4 rounded-2xl"
                  style={{ background: 'linear-gradient(135deg, rgba(234,179,8,0.08), rgba(234,179,8,0.03))', border: '1px solid rgba(234,179,8,0.15)' }}
                >
                  <div className="flex items-center gap-3">
                    <div className="pulse-indicator p-2 rounded-xl bg-yellow-500/15">
                      <Activity className="w-5 h-5 text-yellow-400" />
                    </div>
                    <div>
                      <div className="text-[10px] text-yellow-400 font-bold uppercase tracking-widest font-mono">Risk Assessment</div>
                      <div className="text-sm text-zinc-300 mt-0.5">Mild iron-deficiency anaemia pattern detected</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-3xl font-display font-bold text-yellow-400 tabular-nums">5</div>
                    <div className="text-xs text-yellow-500/60 font-mono">/10</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ── Stats ── */}
        <section className="border-y border-white/5 bg-surface/20 backdrop-blur-sm">
          <div className="max-w-7xl mx-auto px-6 py-14">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-8 divide-x divide-white/5">
              <AnimatedStat value="30+" suffix="" label="CBC Parameters analyzed" />
              <AnimatedStat value="98" suffix="%" label="Extraction accuracy" />
              <AnimatedStat value="5" suffix="min" label="Average analysis time" />
              <AnimatedStat value="12" suffix="+" label="Supported lab formats" />
            </div>
          </div>
        </section>

        {/* ── Features ── */}
        <section id="features" className="max-w-7xl mx-auto px-6 py-24">
          <div className="text-center mb-16">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 text-primary text-xs font-semibold mb-4">
              <FlaskConical className="w-3 h-3" />
              Capabilities
            </div>
            <h2 className="text-3xl md:text-4xl font-display font-bold text-white mb-4">Everything in one clinical workspace</h2>
            <p className="text-zinc-500 max-w-xl mx-auto text-sm leading-relaxed">From raw CBC data to actionable clinical insights — our AI pipeline handles the entire analysis workflow.</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {FEATURES.map((f) => (
              <FeatureCard key={f.title} {...f} />
            ))}
          </div>
        </section>

        {/* ── How it works ── */}
        <section id="how-it-works" className="max-w-7xl mx-auto px-6 py-24">
          <div className="text-center mb-16">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-accent/10 border border-accent/20 text-accent text-xs font-semibold mb-4">
              <TrendingUp className="w-3 h-3" />
              Simple process
            </div>
            <h2 className="text-3xl md:text-4xl font-display font-bold text-white">From upload to insights in 3 steps</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 relative">
            {/* Connector line */}
            <div className="hidden md:block absolute top-14 left-[calc(16.7%+2rem)] right-[calc(16.7%+2rem)] h-px"
              style={{ background: 'linear-gradient(90deg, rgba(14,165,233,0.15), rgba(14,165,233,0.5), rgba(14,165,233,0.15))' }} />

            {STEPS.map((s, i) => (
              <div key={s.step} className="flex flex-col items-center text-center group">
                <div className="relative mb-6">
                  {/* Step ring */}
                  <div
                    className="w-28 h-28 rounded-3xl flex items-center justify-center relative overflow-hidden transition-transform duration-300 group-hover:scale-105"
                    style={{
                      background: `linear-gradient(135deg, ${s.color.includes('primary') ? 'rgba(14,165,233,0.12)' : s.color.includes('violet') ? 'rgba(139,92,246,0.12)' : 'rgba(6,214,160,0.12)'}, rgba(15,22,35,0.5))`,
                      border: `1px solid ${s.color.includes('primary') ? 'rgba(14,165,233,0.2)' : s.color.includes('violet') ? 'rgba(139,92,246,0.2)' : 'rgba(6,214,160,0.2)'}`,
                    }}
                  >
                    <div className={`text-4xl font-display font-bold opacity-10 absolute ${s.color.includes('primary') ? 'text-primary' : s.color.includes('violet') ? 'text-violet-400' : 'text-accent'}`}>{s.step}</div>
                    <div className={`relative z-10 p-3 rounded-xl ${s.color.includes('primary') ? 'bg-primary/15 text-primary' : s.color.includes('violet') ? 'bg-violet-500/15 text-violet-400' : 'bg-accent/15 text-accent'}`}>
                      {s.icon}
                    </div>
                  </div>
                  <div className={`absolute -top-1.5 -right-1.5 w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-bold font-mono text-white ${s.color.includes('primary') ? 'bg-primary' : s.color.includes('violet') ? 'bg-violet-500' : 'bg-accent'}`}>
                    {i + 1}
                  </div>
                </div>
                <h3 className="text-base font-display font-bold text-white mb-2">{s.title}</h3>
                <p className="text-sm text-zinc-500 leading-relaxed max-w-[220px]">{s.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ── Trust & Disclaimer ── */}
        <section id="privacy" className="max-w-7xl mx-auto px-6 py-16">
          <div
            className="rounded-3xl p-8 md:p-12 relative overflow-hidden"
            style={{
              background: 'linear-gradient(135deg, rgba(6,214,160,0.05) 0%, rgba(15,22,35,0.8) 50%, rgba(14,165,233,0.04) 100%)',
              border: '1px solid rgba(6,214,160,0.12)',
            }}
          >
            {/* Corner decoration */}
            <div className="absolute top-0 right-0 w-64 h-64 opacity-30"
              style={{ background: 'radial-gradient(circle at top right, rgba(6,214,160,0.15), transparent 70%)' }} />
            <div className="absolute bottom-0 left-0 w-48 h-48 opacity-20"
              style={{ background: 'radial-gradient(circle at bottom left, rgba(14,165,233,0.15), transparent 70%)' }} />

            <div className="relative">
              <div className="flex items-start gap-4 mb-8">
                <div className="p-3 bg-accent/15 rounded-2xl border border-accent/20 flex-shrink-0">
                  <Lock className="w-5 h-5 text-accent" />
                </div>
                <div>
                  <h3 className="text-xl font-display font-bold text-white mb-1">Privacy & Medical Disclaimer</h3>
                  <p className="text-sm text-zinc-400 leading-relaxed">Your health data is handled responsibly. Please read these important notes.</p>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {TRUST_POINTS.map((pt) => (
                  <div key={pt.text} className="flex items-start gap-3 p-4 rounded-xl bg-white/[0.02] border border-white/5 hover:border-accent/15 transition-colors">
                    <div className="text-accent mt-0.5 flex-shrink-0">{pt.icon}</div>
                    <span className="text-sm text-zinc-300 leading-snug">{pt.text}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* ── Final CTA ── */}
        <section className="max-w-7xl mx-auto px-6 py-24 text-center relative">
          {/* ECG decoration */}
          <div className="absolute left-0 right-0 top-12 opacity-20">
            <EcgLine className="h-16" />
          </div>
          <div className="relative">
            <h2 className="text-4xl md:text-5xl lg:text-6xl font-display font-bold text-white mb-5 leading-tight">
              Ready to understand<br />
              <span style={{ background: 'linear-gradient(135deg, #38BDF8, #0EA5E9, #06D6A0)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}>
                your CBC?
              </span>
            </h2>
            <p className="text-zinc-400 text-lg mb-10 max-w-lg mx-auto">
              Upload your report now. Clinical analysis takes less than 5 minutes.
            </p>
            <Link
              href="/dashboard"
              className="group inline-flex items-center gap-3 px-10 py-4.5 text-white font-semibold rounded-2xl text-base relative overflow-hidden"
              style={{ background: 'linear-gradient(135deg, #0EA5E9, #0284C7, #059669)', boxShadow: '0 12px 40px rgba(14,165,233,0.4), inset 0 1px 0 rgba(255,255,255,0.15)' }}
            >
              <div className="absolute inset-0 bg-white/0 group-hover:bg-white/10 transition-colors" />
              <HeartPulse className="w-5 h-5 relative" />
              <span className="relative">Start Free Analysis</span>
              <ChevronRight className="w-5 h-5 relative group-hover:translate-x-1 transition-transform" />
            </Link>
          </div>
        </section>

        {/* ── Footer ── */}
        <footer className="border-t border-white/5 py-10">
          <div className="max-w-7xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-zinc-600">
            <div className="flex items-center gap-2.5">
              <HeartPulse className="w-4 h-4 text-primary/50" />
              <span className="font-mono text-xs">Health AI · CBC Analyzer</span>
            </div>
            <div className="flex items-center gap-6">
              {!isSignedIn && (
                <Link href="/sign-in" className="hover:text-zinc-400 transition-colors">Sign In</Link>
              )}
            </div>
            <p className="text-xs text-zinc-700">Not a substitute for professional medical advice.</p>
          </div>
        </footer>
      </div>
    </div>
  );
}
