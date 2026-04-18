"use client";

import { useState, useRef, useEffect } from "react";
import axios from "axios";
import { Send, Sparkles, User } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import ReactMarkdown from "react-markdown";

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
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>(
    initialChat && initialChat.length > 0
      ? initialChat
      : [{ role: "assistant", content: "Hello! I have analyzed the report. Ask me anything about it." }]
  );
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef  = useRef<HTMLInputElement>(null);

  // Auto-scroll to latest message
  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, loading]);

  // Focus input on mount
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
        messages: currentMessages, // Send previous messages to help save
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

  return (
    /*
     * h-full so this fills whatever container the parent gives it.
     * Parent (Dashboard chat tab) is flex-col overflow-hidden,
     * so this stretches to fill remaining viewport height.
     */
    <div className="flex flex-1 flex-col h-full min-h-0 overflow-hidden bg-surface/20">

      {/* ── Messages area — scrolls ── */}
      <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar px-5 py-6 md:px-7 md:py-7 space-y-5">
        <AnimatePresence initial={false}>
          {messages.map((msg, idx) => (
            <motion.div
              key={idx}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.18 }}
              className={`flex gap-3.5 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              {/* AI avatar */}
              {msg.role === "assistant" && (
                <div className="w-9 h-9 rounded-2xl bg-primary/15 text-primary flex items-center justify-center shrink-0 border border-primary/20 mt-1">
                  <Sparkles size={14} />
                </div>
              )}

              {/* Bubble */}
              <div className={`
                px-5 py-4 rounded-[24px] max-w-[88%] md:max-w-[78%] text-[15px] md:text-base leading-7 shadow-sm
                ${msg.role === "user"
                  ? "bg-primary text-white rounded-br-none"
                  : "bg-white/[0.05] text-slate-700 rounded-bl-none border border-white/5"
                }
              `}>
                {msg.role === "assistant" ? (
                  <ReactMarkdown
                    components={{
                      h3: ({ children }) => <h3 className="text-base font-bold text-slate-900 mt-3 mb-2">{children}</h3>,
                      ul: ({ children }) => <ul className="list-disc pl-5 mb-2 space-y-1.5">{children}</ul>,
                      li: ({ children }) => <li className="pl-1 text-slate-700">{children}</li>,
                      strong: ({ children }) => <strong className="font-semibold text-slate-900">{children}</strong>,
                      p: ({ children }) => <p className="mb-3 last:mb-0 text-slate-700">{children}</p>,
                      code: ({ children }) => (
                        <code className="bg-slate-100 px-1.5 py-0.5 rounded text-xs font-mono text-slate-700">{children}</code>
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
                <div className="w-9 h-9 rounded-2xl bg-zinc-700 flex items-center justify-center shrink-0 mt-1">
                  <User size={14} className="text-slate-600" />
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
            className="flex gap-3.5 justify-start"
          >
            <div className="w-9 h-9 rounded-2xl bg-primary/15 text-primary flex items-center justify-center shrink-0 border border-primary/20">
              <Sparkles size={14} />
            </div>
            <div className="bg-white/[0.05] px-5 py-4 rounded-[24px] rounded-bl-none border border-white/5 flex items-center gap-3">
              <span className="flex gap-1">
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="w-1.5 h-1.5 rounded-full bg-zinc-500 animate-bounce"
                    style={{ animationDelay: `${i * 0.15}s` }}
                  />
                ))}
              </span>
              <span className="text-sm text-zinc-500">Analyzing context...</span>
            </div>
          </motion.div>
        )}

        {/* Scroll anchor */}
        <div ref={scrollRef} />
      </div>

      {/* ── Input area — fixed at bottom ── */}
      <div className="flex-shrink-0 px-5 py-3 md:px-6 md:py-4 border-t border-white/5 bg-surface/40 backdrop-blur-sm">
        <form onSubmit={handleSend} className="relative flex items-center gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a follow-up question about your report..."
            disabled={loading}
            className="flex-1 bg-black/25 border border-white/10 rounded-2xl py-4 pl-5 pr-14 text-[15px] md:text-base text-slate-900 placeholder-zinc-500 focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/40 transition-all duration-200 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            aria-label="Send message"
            className="absolute right-3 top-1/2 -translate-y-1/2 w-10 h-10 flex items-center justify-center bg-primary hover:bg-primaryDark text-white rounded-xl transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed hover:scale-105 active:scale-95 shadow-md shadow-primary/20"
          >
            <Send size={16} />
          </button>
        </form>
        <p className="text-[11px] text-zinc-600 text-center mt-3">
          Answers grounded in your report data via RAG
        </p>
      </div>
    </div>
  );
}
