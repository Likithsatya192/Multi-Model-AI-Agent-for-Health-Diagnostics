"use client";

import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { AlertTriangle } from "lucide-react";

interface ConfirmModalProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmModal({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  onConfirm,
  onCancel,
}: ConfirmModalProps) {
  const cancelRef = useRef<HTMLButtonElement>(null);

  // Focus Cancel on open — safer default for destructive actions
  useEffect(() => {
    if (open) cancelRef.current?.focus();
  }, [open]);

  // Dismiss on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onCancel]);

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Scrim */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-[100] bg-black/60 backdrop-blur-sm"
            onClick={onCancel}
            aria-hidden="true"
          />

          {/* Dialog */}
          <div className="fixed inset-0 z-[101] flex items-center justify-center p-4 pointer-events-none">
            <motion.div
              role="dialog"
              aria-modal="true"
              aria-labelledby="confirm-modal-title"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.15 }}
              className="bg-surface border border-white/10 rounded-2xl p-7 w-full max-w-sm shadow-2xl pointer-events-auto"
            >
              <div className="w-11 h-11 bg-error/10 border border-error/20 rounded-xl flex items-center justify-center mb-4">
                <AlertTriangle className="w-5 h-5 text-error" />
              </div>
              <h2
                id="confirm-modal-title"
                className="text-base font-display font-bold text-slate-900 mb-2"
              >
                {title}
              </h2>
              <p className="text-sm text-slate-600 leading-relaxed mb-6">{description}</p>
              <div className="flex gap-2">
                <button
                  ref={cancelRef}
                  onClick={onCancel}
                  className="flex-1 py-2.5 rounded-xl bg-white/5 border border-white/10 text-sm font-medium text-slate-700 hover:bg-white/10 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={onConfirm}
                  className="flex-1 py-2.5 rounded-xl bg-error/15 border border-error/30 text-sm font-semibold text-red-400 hover:bg-error/25 transition-colors"
                >
                  {confirmLabel}
                </button>
              </div>
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  );
}
