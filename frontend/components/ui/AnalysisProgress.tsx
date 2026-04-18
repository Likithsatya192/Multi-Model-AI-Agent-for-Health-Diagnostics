"use client";

import { useState, useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { CheckCircle, Loader2, BrainCircuit } from "lucide-react";

const STEPS: { label: string; endAt: number }[] = [
  { label: "Extracting CBC parameters",     endAt: 15  },
  { label: "Building RAG knowledge base",   endAt: 55  },
  { label: "Assessing risk & patterns",     endAt: 110 },
  { label: "Generating clinical synthesis", endAt: 180 },
  { label: "Compiling recommendations",     endAt: 270 },
];

const TOTAL_SECONDS = 300;

interface AnalysisProgressProps {
  active: boolean;
}

export function AnalysisProgress({ active }: AnalysisProgressProps) {
  const [elapsed, setElapsed] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!active) {
      setElapsed(0);
      if (intervalRef.current) clearInterval(intervalRef.current);
      return;
    }
    setElapsed(0);
    intervalRef.current = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [active]);

  if (!active) return null;

  const activeIdx = STEPS.findIndex((s) => elapsed < s.endAt);
  const resolvedIdx = activeIdx === -1 ? STEPS.length - 1 : activeIdx;
  const progress = Math.min((elapsed / TOTAL_SECONDS) * 100, 95);

  const mm = String(Math.floor(elapsed / 60)).padStart(2, "0");
  const ss = String(elapsed % 60).padStart(2, "0");

  return (
    <div className="h-full flex flex-col items-center justify-center p-8">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="w-full max-w-md"
      >
        {/* Icon */}
        <div className="flex justify-center mb-6">
          <div className="w-16 h-16 bg-primary/10 border border-primary/20 rounded-2xl flex items-center justify-center">
            <BrainCircuit className="w-8 h-8 text-primary" />
          </div>
        </div>

        <h2 className="text-xl font-display font-bold text-slate-900 text-center mb-2">
          Analyzing your report
        </h2>
        <p className="text-sm text-zinc-500 text-center mb-8">
          AI is processing your CBC data — this takes up to 5 minutes
        </p>

        {/* Progress bar */}
        <div className="h-1 bg-slate-200 rounded-full mb-6 overflow-hidden">
          <motion.div
            className="h-full bg-gradient-to-r from-primary to-primaryDark rounded-full"
            animate={{ width: `${progress}%` }}
            transition={{ duration: 1, ease: "linear" }}
          />
        </div>

        {/* Steps */}
        <div className="space-y-2">
          {STEPS.map((step, idx) => {
            const done = idx < resolvedIdx;
            const isActive = idx === resolvedIdx;
            return (
              <div
                key={step.label}
                className={`flex items-center gap-3 px-4 py-2.5 rounded-xl border text-sm transition-all ${
                  done
                    ? "bg-green-500/5 border-green-500/15 text-green-400"
                    : isActive
                    ? "bg-primary/10 border-primary/20 text-primaryGlow"
                    : "bg-white/[0.02] border-white/5 text-slate-500"
                }`}
              >
                {done ? (
                  <CheckCircle className="w-4 h-4 shrink-0" />
                ) : isActive ? (
                  <Loader2 className="w-4 h-4 shrink-0 animate-spin" />
                ) : (
                  <span className="w-4 h-4 shrink-0 flex items-center justify-center text-[10px] font-bold">
                    {idx + 1}
                  </span>
                )}
                <span className="flex-1 font-medium">{step.label}</span>
                {done && (
                  <span className="text-[11px] font-mono opacity-50">done</span>
                )}
                {isActive && (
                  <span className="text-[11px] font-mono opacity-60">running</span>
                )}
              </div>
            );
          })}
        </div>

        <p className="text-center text-xs text-slate-500 mt-6 font-mono">
          Elapsed: {mm}:{ss} · Please keep this tab open
        </p>
      </motion.div>
    </div>
  );
}
