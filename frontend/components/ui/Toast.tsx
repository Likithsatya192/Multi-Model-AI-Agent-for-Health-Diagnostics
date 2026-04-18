"use client";

import { createContext, useContext, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { CheckCircle, XCircle, Info, X } from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

type ToastType = "success" | "error" | "info";

interface ToastItem {
  id: string;
  type: ToastType;
  title: string;
  message?: string;
}

interface ToastContextValue {
  success: (title: string, message?: string) => void;
  error: (title: string, message?: string) => void;
  info: (title: string, message?: string) => void;
}

// ─── Context ──────────────────────────────────────────────────────────────────

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const TOAST_STYLES: Record<ToastType, { wrapper: string; icon: React.ReactNode }> = {
  success: {
    wrapper: "bg-green-500/10 border-green-500/20",
    icon: <CheckCircle className="w-4 h-4 text-green-400 shrink-0 mt-0.5" />,
  },
  error: {
    wrapper: "bg-red-500/10 border-red-500/20",
    icon: <XCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />,
  },
  info: {
    wrapper: "bg-primaryGlow/10 border-primaryGlow/20",
    icon: <Info className="w-4 h-4 text-primaryGlow shrink-0 mt-0.5" />,
  },
};

// ─── Provider ─────────────────────────────────────────────────────────────────

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const add = useCallback(
    (type: ToastType, title: string, message?: string) => {
      const id = Math.random().toString(36).slice(2);
      setToasts((prev) => [...prev, { id, type, title, message }]);
      setTimeout(() => dismiss(id), 4000);
    },
    [dismiss]
  );

  const ctx: ToastContextValue = {
    success: (title, message) => add("success", title, message),
    error: (title, message) => add("error", title, message),
    info: (title, message) => add("info", title, message),
  };

  return (
    <ToastContext.Provider value={ctx}>
      {children}
      {/* Notification stack — bottom-right, above all content */}
      <div
        role="region"
        aria-live="polite"
        aria-label="Notifications"
        className="fixed bottom-4 right-4 z-[9999] flex flex-col gap-2 w-80 max-w-[calc(100vw-2rem)] pointer-events-none"
      >
        <AnimatePresence initial={false}>
          {toasts.map((toast) => {
            const s = TOAST_STYLES[toast.type];
            return (
              <motion.div
                key={toast.id}
                initial={{ opacity: 0, y: 16, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 8, scale: 0.95 }}
                transition={{ duration: 0.2 }}
                className={`flex items-start gap-3 px-4 py-3 rounded-xl border backdrop-blur-md shadow-xl pointer-events-auto ${s.wrapper}`}
              >
                {s.icon}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-slate-900">{toast.title}</p>
                  {toast.message && (
                    <p className="text-xs text-slate-600 mt-0.5 leading-relaxed">{toast.message}</p>
                  )}
                </div>
                <button
                  onClick={() => dismiss(toast.id)}
                  aria-label="Dismiss notification"
                  className="p-0.5 text-zinc-500 hover:text-slate-900 transition-colors shrink-0"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}
