"use client";

import { useState, useRef, useEffect } from "react";
import axios from "axios";
import { Send, Sparkles, User } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import ReactMarkdown from "react-markdown";
import { useTheme } from "./ui/ThemeProvider";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface ChatComponentProps {
  collectionName: string;
  sessionId: string;
  reportId?: string;
  initialChat?: Message[];
}

export default function ChatComponent({ collectionName, sessionId, reportId, initialChat }: ChatComponentProps) {
  const { theme } = useTheme();
  const isDark = theme === "dark";

  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>(
    initialChat && initialChat.length > 0
      ? initialChat
      : [{ role: "assistant", content: "Hello! I have analyzed the report. Ask me anything about it." }]
  );
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef  = useRef<HTMLInputElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, loading]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !collectionName || loading) return;

    const userMessage = input.trim();
    setInput("");
    const currentMessages = [...messages];
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setLoading(true);

    try {
      const response = await axios.post("/api/query", {
        question: userMessage,
        collection_name: collectionName,
        session_id: sessionId,
        report_id: reportId,
        messages: currentMessages,
      });
      setMessages((prev) => [...prev, { role: "assistant", content: response.data.answer }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Sorry, I encountered an error. Please try again." },
      ]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  // Theme-aware style tokens
  const aiBubbleBg    = isDark ? "rgba(255,255,255,0.07)" : "rgba(241,245,249,0.95)";
  const aiBubbleBorder = isDark ? "rgba(255,255,255,0.1)" : "rgba(148,163,184,0.25)";
  const aiText        = isDark ? "#e4e4e7" : "#1e293b";   // zinc-200 / slate-800
  const aiHeading     = isDark ? "#ffffff"  : "#0f172a";
  const aiSubtext     = isDark ? "#a1a1aa"  : "#475569";   // zinc-400 / slate-600
  const inputBg       = isDark ? "rgba(0,0,0,0.25)"        : "rgba(255,255,255,0.9)";
  const inputBorder   = isDark ? "rgba(255,255,255,0.1)"   : "rgba(148,163,184,0.3)";
  const inputText     = isDark ? "#e4e4e7"  : "#1e293b";
  const inputPlaceholder = isDark ? "#71717a" : "#94a3b8";
  const footerBg      = isDark ? "rgba(255,255,255,0.02)"  : "rgba(241,245,249,0.8)";
  const footerBorder  = isDark ? "rgba(255,255,255,0.05)"  : "rgba(148,163,184,0.2)";

  return (
    <div className="flex flex-1 flex-col h-full min-h-0 overflow-hidden">

      {/* ── Messages area ── */}
      <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar px-4 py-5 md:px-6 md:py-6 space-y-4">
        <AnimatePresence initial={false}>
          {messages.map((msg, idx) => (
            <motion.div
              key={idx}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.18 }}
              className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              {/* AI avatar */}
              {msg.role === "assistant" && (
                <div className="w-8 h-8 rounded-xl bg-primary/15 text-primary flex items-center justify-center shrink-0 border border-primary/20 mt-1">
                  <Sparkles size={13} />
                </div>
              )}

              {/* Bubble */}
              <div
                className={`px-5 py-3.5 rounded-[20px] max-w-[88%] md:max-w-[80%] text-[15px] leading-[1.7] shadow-sm ${
                  msg.role === "user" ? "rounded-br-none" : "rounded-bl-none"
                }`}
                style={
                  msg.role === "user"
                    ? { background: "#0077B6", color: "#ffffff" }
                    : {
                        background: aiBubbleBg,
                        border: `1px solid ${aiBubbleBorder}`,
                        color: aiText,
                      }
                }
              >
                {msg.role === "assistant" ? (
                  <ReactMarkdown
                    components={{
                      h3: ({ children }) => <h3 style={{ color: aiHeading }} className="text-[15px] font-bold mt-3 mb-2">{children}</h3>,
                      h2: ({ children }) => <h2 style={{ color: aiHeading }} className="text-base font-bold mt-4 mb-2">{children}</h2>,
                      ul: ({ children }) => <ul className="list-disc pl-5 mb-2 space-y-1.5">{children}</ul>,
                      ol: ({ children }) => <ol className="list-decimal pl-5 mb-2 space-y-1.5">{children}</ol>,
                      li: ({ children }) => <li style={{ color: aiText }} className="pl-1 leading-relaxed">{children}</li>,
                      strong: ({ children }) => <strong style={{ color: aiHeading }} className="font-semibold">{children}</strong>,
                      em: ({ children }) => <em style={{ color: aiSubtext }} className="italic">{children}</em>,
                      p: ({ children }) => <p style={{ color: aiText }} className="mb-2.5 last:mb-0 leading-relaxed">{children}</p>,
                      code: ({ children }) => (
                        <code
                          style={{
                            background: isDark ? "rgba(255,255,255,0.1)" : "rgba(15,23,42,0.08)",
                            color: isDark ? "#e2e8f0" : "#334155",
                          }}
                          className="px-1.5 py-0.5 rounded text-xs font-mono"
                        >
                          {children}
                        </code>
                      ),
                      blockquote: ({ children }) => (
                        <blockquote style={{ color: aiSubtext }} className="border-l-2 border-primary/50 pl-3 my-2 italic">{children}</blockquote>
                      ),
                    }}
                  >
                    {msg.content}
                  </ReactMarkdown>
                ) : (
                  <span>{msg.content}</span>
                )}
              </div>

              {/* User avatar */}
              {msg.role === "user" && (
                <div
                  className="w-8 h-8 rounded-xl flex items-center justify-center shrink-0 mt-1"
                  style={{
                    background: isDark ? "rgba(113,113,122,0.4)" : "rgba(148,163,184,0.25)",
                    border: isDark ? "1px solid rgba(255,255,255,0.08)" : "1px solid rgba(148,163,184,0.3)",
                  }}
                >
                  <User size={13} style={{ color: isDark ? "#a1a1aa" : "#64748b" }} />
                </div>
              )}
            </motion.div>
          ))}
        </AnimatePresence>

        {/* Loading indicator */}
        {loading && (
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex gap-3 justify-start"
          >
            <div className="w-8 h-8 rounded-xl bg-primary/15 text-primary flex items-center justify-center shrink-0 border border-primary/20">
              <Sparkles size={13} />
            </div>
            <div
              className="px-5 py-3.5 rounded-[20px] rounded-bl-none flex items-center gap-3"
              style={{ background: aiBubbleBg, border: `1px solid ${aiBubbleBorder}` }}
            >
              <span className="flex gap-1">
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="w-1.5 h-1.5 rounded-full bg-primary/60 animate-bounce"
                    style={{ animationDelay: `${i * 0.15}s` }}
                  />
                ))}
              </span>
              <span className="text-sm" style={{ color: aiSubtext }}>Analyzing context...</span>
            </div>
          </motion.div>
        )}

        <div ref={scrollRef} />
      </div>

      {/* ── Input area ── */}
      <div
        className="flex-shrink-0 px-4 py-3 md:px-5 md:py-4 backdrop-blur-sm"
        style={{ background: footerBg, borderTop: `1px solid ${footerBorder}` }}
      >
        <form onSubmit={handleSend} className="relative flex items-center gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask anything about your CBC report..."
            disabled={loading}
            className="flex-1 rounded-2xl py-3.5 pl-5 pr-14 text-[15px] focus:outline-none focus:ring-1 focus:ring-primary/40 transition-all duration-200 disabled:opacity-50"
            style={{
              background: inputBg,
              border: `1px solid ${inputBorder}`,
              color: inputText,
            }}
            onFocus={e => (e.currentTarget.style.borderColor = "rgba(0,119,182,0.5)")}
            onBlur={e => (e.currentTarget.style.borderColor = inputBorder)}
          />
          {/* Placeholder color via inline style workaround */}
          <style>{`input::placeholder { color: ${inputPlaceholder}; }`}</style>
          <button
            type="submit"
            disabled={loading || !input.trim()}
            aria-label="Send message"
            className="absolute right-3 top-1/2 -translate-y-1/2 w-9 h-9 flex items-center justify-center bg-primary hover:bg-primaryDark text-white rounded-xl transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed hover:scale-105 active:scale-95 shadow-md shadow-primary/20"
          >
            <Send size={15} />
          </button>
        </form>
        <p className="text-[11px] text-center mt-2" style={{ color: aiSubtext }}>
          Answers grounded in your report via RAG
        </p>
      </div>
    </div>
  );
}
