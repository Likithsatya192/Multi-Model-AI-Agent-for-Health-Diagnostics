"use client";

import { useState, useRef, useEffect } from "react";
import axios from "axios";
import { Send, Loader2, Sparkles, User } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import ReactMarkdown from "react-markdown";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface ChatComponentProps {
  collectionName: string;
  sessionId: string;
}

export default function ChatComponent({ collectionName, sessionId }: ChatComponentProps) {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", content: "Hello! I have analyzed the report. Ask me anything about it." },
  ]);
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
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setLoading(true);

    try {
      const response = await axios.post("/api/query", {
        question: userMessage,
        collection_name: collectionName,
        session_id: sessionId,
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
    <div className="flex flex-col h-full bg-surface/20">

      {/* ── Messages area — scrolls ── */}
      <div className="flex-1 overflow-y-auto custom-scrollbar px-5 py-5 space-y-4">
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
                <div className="w-7 h-7 rounded-full bg-primary/20 text-primary flex items-center justify-center shrink-0 border border-primary/20 mt-1">
                  <Sparkles size={12} />
                </div>
              )}

              {/* Bubble */}
              <div className={`
                px-4 py-3 rounded-2xl max-w-[82%] text-sm leading-relaxed shadow-sm
                ${msg.role === "user"
                  ? "bg-primary text-white rounded-br-none"
                  : "bg-white/[0.05] text-zinc-200 rounded-bl-none border border-white/5"
                }
              `}>
                {msg.role === "assistant" ? (
                  <ReactMarkdown
                    components={{
                      h3: ({ children }) => <h3 className="text-sm font-bold text-white mt-3 mb-1.5">{children}</h3>,
                      ul: ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-1">{children}</ul>,
                      li: ({ children }) => <li className="pl-1 text-zinc-300">{children}</li>,
                      strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
                      p: ({ children }) => <p className="mb-2 last:mb-0 text-zinc-300">{children}</p>,
                      code: ({ children }) => (
                        <code className="bg-white/10 px-1.5 py-0.5 rounded text-xs font-mono text-zinc-300">{children}</code>
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
                <div className="w-7 h-7 rounded-full bg-zinc-700 flex items-center justify-center shrink-0 mt-1">
                  <User size={12} className="text-zinc-300" />
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
            <div className="w-7 h-7 rounded-full bg-primary/15 text-primary flex items-center justify-center shrink-0 border border-primary/20">
              <Sparkles size={12} />
            </div>
            <div className="bg-white/[0.05] px-4 py-3 rounded-2xl rounded-bl-none border border-white/5 flex items-center gap-2.5">
              <span className="flex gap-1">
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="w-1.5 h-1.5 rounded-full bg-zinc-500 animate-bounce"
                    style={{ animationDelay: `${i * 0.15}s` }}
                  />
                ))}
              </span>
              <span className="text-xs text-zinc-500">Analyzing context...</span>
            </div>
          </motion.div>
        )}

        {/* Scroll anchor */}
        <div ref={scrollRef} />
      </div>

      {/* ── Input area — fixed at bottom ── */}
      <div className="flex-shrink-0 px-4 py-3 border-t border-white/5 bg-surface/40 backdrop-blur-sm">
        <form onSubmit={handleSend} className="relative flex items-center gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a follow-up question about your report..."
            disabled={loading}
            className="flex-1 bg-black/25 border border-white/10 rounded-xl py-3 pl-4 pr-12 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/40 transition-all duration-200 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            aria-label="Send message"
            className="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 flex items-center justify-center bg-primary hover:bg-primaryDark text-white rounded-lg transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed hover:scale-105 active:scale-95 shadow-md shadow-primary/20"
          >
            <Send size={15} />
          </button>
        </form>
        <p className="text-[10px] text-zinc-600 text-center mt-2">
          Answers grounded in your report data via RAG
        </p>
      </div>
    </div>
  );
}
