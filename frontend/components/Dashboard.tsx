"use client";

import { useState, useEffect, useCallback } from "react";
import { v4 as uuidv4 } from "uuid";
import { useUser, useClerk } from "@clerk/nextjs";
import axios from "axios";
import {
  LogOut, Upload, CheckCircle, Clock,
  FileText, Settings, Camera, X, Loader2,
  Edit2, PlusCircle, FileSearch,
  Check, ShieldAlert, Activity, Sparkles, BrainCircuit,
  Trash2, Menu, BarChart2, HeartPulse, Microscope, FlaskConical,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import ReactMarkdown from "react-markdown";
import ChatComponent from "./ChatComponent";
import { ConfirmModal } from "./ui/ConfirmModal";
import { AnalysisProgress } from "./ui/AnalysisProgress";
import { useToast } from "./ui/Toast";
import { CbcChart } from "./ui/CbcChart";

// ─── Types ───────────────────────────────────────────────────────────────────

interface ReportSummary {
  id: string;
  filename: string;
  title: string;
  risk_score: number;
  created_at: string;
}

interface ReportDetail extends ReportSummary {
  rag_collection_name: string;
  risk_rationale: string | string[];
  param_interpretation: Record<string, any>;
  synthesis_report: string | string[];
  recommendations: string[];
  patterns: string[];
  context_analysis: string;
  errors: string[];
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function groupByDate(reports: ReportSummary[]) {
  const now = new Date();
  const today = now.toDateString();
  const yesterday = new Date(now.getTime() - 86400000).toDateString();
  const week = new Date(now.getTime() - 7 * 86400000);
  const month = new Date(now.getTime() - 30 * 86400000);

  const groups: Record<string, ReportSummary[]> = {
    Today: [], Yesterday: [], "Last 7 Days": [], "Last 30 Days": [], Older: [],
  };

  for (const r of reports) {
    const d = new Date(r.created_at);
    const ds = d.toDateString();
    if (ds === today)         groups["Today"].push(r);
    else if (ds === yesterday) groups["Yesterday"].push(r);
    else if (d >= week)        groups["Last 7 Days"].push(r);
    else if (d >= month)       groups["Last 30 Days"].push(r);
    else                       groups["Older"].push(r);
  }
  return groups;
}

function riskMeta(score: number) {
  if (score > 6) return { color: "text-red-400",    bg: "bg-red-500/10",    border: "border-red-500/20",    label: "High" };
  if (score > 3) return { color: "text-yellow-400", bg: "bg-yellow-500/10", border: "border-yellow-500/20", label: "Moderate" };
  return          { color: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/20", label: "Low" };
}

function SafeMarkdown({ content }: { content: string }) {
  return (
    <ReactMarkdown
      components={{
        p:      ({ children }) => <p className="mb-3 last:mb-0 text-sm text-zinc-300 leading-relaxed">{children}</p>,
        strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
        ul:     ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-1">{children}</ul>,
        li:     ({ children }) => <li className="text-sm text-zinc-300 pl-1">{children}</li>,
        h3:     ({ children }) => <h3 className="text-base font-display font-bold text-white mt-4 mb-2">{children}</h3>,
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

// ─── Component ───────────────────────────────────────────────────────────────

export default function Dashboard() {
  const { user: clerkUser } = useUser();
  const { signOut } = useClerk();
  const toast = useToast();

  const userEmail = clerkUser?.primaryEmailAddress?.emailAddress || "";

  const [view, setView] = useState<"upload" | "report">("upload");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [selectedReport, setSelectedReport] = useState<ReportDetail | null>(null);
  const [loadingReports, setLoadingReports] = useState(true);
  const [loadingReport, setLoadingReport] = useState(false);
  const [activeReportId, setActiveReportId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [sessionId, setSessionId] = useState(() => uuidv4());
  const [confirmDelete, setConfirmDelete] = useState<{ id: string } | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [userName, setUserName] = useState("");
  const [updatingProfile, setUpdatingProfile] = useState(false);
  const [reportTab, setReportTab] = useState<"overview" | "chart" | "chat">("overview");
  const [dragOver, setDragOver] = useState(false);

  useEffect(() => {
    if (clerkUser) setUserName(clerkUser.fullName || "");
  }, [clerkUser?.id]);

  const fetchReports = useCallback(async () => {
    setLoadingReports(true);
    try {
      const res = await axios.get<ReportSummary[]>("/api/reports");
      setReports(res.data);
    } catch {
      toast.error("Failed to load reports", "Please refresh the page.");
    } finally {
      setLoadingReports(false);
    }
  }, []);

  useEffect(() => { fetchReports(); }, [fetchReports]);

  const handleNewAnalysis = () => {
    setView("upload"); setSelectedReport(null); setActiveReportId(null);
    setFile(null); setSessionId(uuidv4()); setReportTab("overview");
  };

  const handleSelectReport = async (id: string) => {
    if (id === activeReportId) return;
    setActiveReportId(id); setLoadingReport(true); setView("report"); setReportTab("overview");
    try {
      const res = await axios.get<ReportDetail>(`/api/reports/${id}`);
      setSelectedReport(res.data); setSessionId(uuidv4());
    } catch {
      toast.error("Failed to load report", "Please try again.");
    } finally { setLoadingReport(false); }
  };

  const requestDeleteReport = (id: string, e: React.MouseEvent) => {
    e.stopPropagation(); setConfirmDelete({ id });
  };

  const handleDeleteReport = async () => {
    if (!confirmDelete) return;
    const { id } = confirmDelete; setConfirmDelete(null);
    try {
      await axios.delete(`/api/reports/${id}`);
      setReports((prev) => prev.filter((r) => r.id !== id));
      if (activeReportId === id) { setSelectedReport(null); setActiveReportId(null); setView("upload"); }
      toast.success("Report deleted");
    } catch { toast.error("Failed to delete report", "Please try again."); }
  };

  const handleAnalysis = async () => {
    if (!file) return;
    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);
    formData.append("session_id", sessionId);
    try {
      const response = await axios.post<ReportDetail>("/api/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" }, timeout: 300000,
      });
      const data = response.data;
      if (data.errors?.length > 0) toast.error("Analysis completed with issues", data.errors.join(" · "));
      else toast.success("Analysis complete", "Your CBC report has been analyzed.");
      setSelectedReport(data); setActiveReportId(data.id ?? null);
      setView("report"); setReportTab("overview"); setFile(null);
      if (data.id) {
        const summary: ReportSummary = {
          id: data.id, filename: data.filename, title: data.title,
          risk_score: data.risk_score, created_at: data.created_at ?? new Date().toISOString(),
        };
        setReports((prev) => [summary, ...prev]);
      }
    } catch (error: any) {
      let msg = "Please check the backend is running.";
      if (error.response) msg = `Server ${error.response.status}: ${JSON.stringify(error.response.data)}`;
      else if (error.request) msg = "No response from server. Is the backend running?";
      else msg = error.message;
      toast.error("Analysis failed", msg);
    } finally { setUploading(false); }
  };

  const handleUpdateProfile = async (e: React.FormEvent) => {
    e.preventDefault(); setUpdatingProfile(true);
    try {
      await clerkUser?.update({ firstName: userName });
      setIsEditing(false); toast.success("Profile updated");
    } catch (error: any) {
      toast.error("Failed to update profile", error.message);
    } finally { setUpdatingProfile(false); }
  };

  const handlePhotoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f || !clerkUser) return;
    try {
      await clerkUser.setProfileImage({ file: f });
      toast.success("Profile photo updated");
    } catch (error: any) { toast.error("Failed to update photo", error.message); }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault(); setDragOver(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) setFile(dropped);
  };

  const groups = groupByDate(reports);

  // ─── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-background text-white font-sans selection:bg-primary/30 relative overflow-hidden">

      {/* ── Ambient layers ── */}
      <div className="fixed inset-0 pointer-events-none z-0" aria-hidden="true">
        <div className="absolute inset-0 medical-grid opacity-40" />
        <div className="glow-orb absolute top-[-20%] left-[-10%] w-[800px] h-[800px] rounded-full"
          style={{ background: "radial-gradient(circle, rgba(14,165,233,0.1) 0%, transparent 70%)" }} />
        <div className="glow-orb glow-orb-2 absolute bottom-[-20%] right-[-10%] w-[700px] h-[700px] rounded-full"
          style={{ background: "radial-gradient(circle, rgba(6,214,160,0.06) 0%, transparent 70%)" }} />
      </div>

      <div className="relative z-10 w-full h-screen flex overflow-hidden">

        {/* ════════════════════ SIDEBAR ════════════════════ */}
        <AnimatePresence initial={false}>
          {sidebarOpen && (
            <motion.aside
              key="sidebar"
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 272, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: 0.22, ease: "easeInOut" }}
              className="flex-shrink-0 h-full flex flex-col overflow-hidden border-r"
              style={{
                background: "linear-gradient(180deg, rgba(15,22,35,0.95) 0%, rgba(10,16,28,0.98) 100%)",
                borderColor: "rgba(14,165,233,0.08)",
                backdropFilter: "blur(24px)",
              }}
            >
              {/* Logo row */}
              <div className="p-4 flex-shrink-0 border-b" style={{ borderColor: "rgba(255,255,255,0.05)" }}>
                <div className="flex items-center gap-3 px-1">
                  <div className="relative p-2 bg-primary/15 rounded-xl border border-primary/20">
                    <HeartPulse className="text-primary w-4.5 h-4.5" />
                    <div className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-accent animate-pulse" />
                  </div>
                  <div>
                    <span className="text-sm font-display font-bold text-white tracking-tight block">Health AI</span>
                    <span className="text-[10px] text-primary/50 font-mono">CBC Analyzer</span>
                  </div>
                </div>
              </div>

              {/* New Analysis button */}
              <div className="p-3 flex-shrink-0">
                <button
                  onClick={handleNewAnalysis}
                  className="w-full flex items-center gap-2.5 px-4 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 group"
                  style={{
                    background: "linear-gradient(135deg, rgba(14,165,233,0.12), rgba(14,165,233,0.06))",
                    border: "1px solid rgba(14,165,233,0.2)",
                    color: "#38BDF8",
                  }}
                  onMouseEnter={e => (e.currentTarget.style.background = "linear-gradient(135deg, rgba(14,165,233,0.2), rgba(14,165,233,0.1))")}
                  onMouseLeave={e => (e.currentTarget.style.background = "linear-gradient(135deg, rgba(14,165,233,0.12), rgba(14,165,233,0.06))")}
                >
                  <PlusCircle className="w-4 h-4" />
                  New Analysis
                </button>
              </div>

              {/* Report history */}
              <div className="flex-1 overflow-y-auto custom-scrollbar px-2 pb-2 min-h-0">
                {loadingReports ? (
                  <div className="flex items-center justify-center py-12">
                    <div className="relative w-8 h-8">
                      <div className="absolute inset-0 rounded-full border-t border-primary animate-spin" />
                      <HeartPulse className="absolute inset-0 m-auto w-3 h-3 text-primary/50" />
                    </div>
                  </div>
                ) : reports.length === 0 ? (
                  <div className="text-center py-12 px-4">
                    <div className="w-12 h-12 rounded-2xl bg-surface/60 border border-white/5 flex items-center justify-center mx-auto mb-3">
                      <FileSearch className="w-5 h-5 text-zinc-600" />
                    </div>
                    <p className="text-xs text-zinc-500 leading-relaxed">No reports yet.<br />Upload your first CBC report.</p>
                  </div>
                ) : (
                  Object.entries(groups).map(([label, items]) =>
                    items.length === 0 ? null : (
                      <div key={label} className="mb-1">
                        <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-widest px-3 py-2">
                          {label}
                        </p>
                        {items.map((report) => {
                          const rm = riskMeta(report.risk_score);
                          const isActive = activeReportId === report.id;
                          return (
                            <div
                              key={report.id}
                              onClick={() => handleSelectReport(report.id)}
                              role="button"
                              aria-label={`View report: ${report.title}`}
                              className="group relative flex flex-col gap-1 px-3 py-2.5 rounded-xl cursor-pointer transition-all duration-150 mb-0.5"
                              style={{
                                background: isActive
                                  ? "linear-gradient(135deg, rgba(14,165,233,0.12), rgba(14,165,233,0.06))"
                                  : "transparent",
                                border: isActive
                                  ? "1px solid rgba(14,165,233,0.25)"
                                  : "1px solid transparent",
                              }}
                              onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = "rgba(255,255,255,0.03)"; }}
                              onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = "transparent"; }}
                            >
                              {/* Active indicator line */}
                              {isActive && (
                                <div className="absolute left-0 top-2 bottom-2 w-0.5 rounded-full bg-primary" />
                              )}
                              <div className="flex items-start justify-between gap-2">
                                <p className="text-sm text-white font-medium leading-tight truncate flex-1">{report.title}</p>
                                <button
                                  onClick={(e) => requestDeleteReport(report.id, e)}
                                  aria-label="Delete report"
                                  className="opacity-0 group-hover:opacity-100 p-1 rounded-md hover:bg-red-500/15 hover:text-red-400 text-zinc-600 transition-all flex-shrink-0"
                                >
                                  <Trash2 className="w-3 h-3" />
                                </button>
                              </div>
                              <div className="flex items-center gap-2">
                                <span className="text-[11px] text-zinc-600 font-mono truncate flex-1">{report.filename}</span>
                                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-md border flex-shrink-0 ${rm.color} ${rm.bg} ${rm.border}`}>
                                  {report.risk_score}/10
                                </span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )
                  )
                )}
              </div>

              {/* User profile footer */}
              <div className="p-3 flex-shrink-0 border-t" style={{ borderColor: "rgba(255,255,255,0.05)" }}>
                <div
                  className="flex items-center gap-3 px-3 py-2.5 rounded-xl cursor-pointer transition-all duration-200 group"
                  onClick={() => setShowSettings(true)}
                  role="button"
                  aria-label="Open settings"
                  onMouseEnter={e => (e.currentTarget.style.background = "rgba(255,255,255,0.04)")}
                  onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                >
                  <div className="w-8 h-8 rounded-full bg-zinc-800 border border-white/10 overflow-hidden flex-shrink-0">
                    {clerkUser?.imageUrl ? (
                      <img src={clerkUser.imageUrl} alt={clerkUser?.fullName || "User"} className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-primary to-primaryDark text-white text-xs font-bold">
                        {(clerkUser?.fullName || "U")[0].toUpperCase()}
                      </div>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-white truncate group-hover:text-primary transition-colors">{clerkUser?.fullName || "User"}</p>
                    <p className="text-[10px] text-zinc-500 truncate">{userEmail}</p>
                  </div>
                  <Settings className="w-3.5 h-3.5 text-zinc-600 group-hover:text-zinc-400 transition-colors flex-shrink-0 group-hover:rotate-45 duration-300" />
                </div>
              </div>
            </motion.aside>
          )}
        </AnimatePresence>

        {/* ════════════════════ MAIN AREA ════════════════════ */}
        <div className="flex-1 flex flex-col h-full overflow-hidden min-w-0">

          {/* Top bar */}
          <div
            className="flex items-center gap-3 px-4 py-3 flex-shrink-0 border-b"
            style={{
              background: "rgba(7,9,15,0.7)",
              backdropFilter: "blur(20px)",
              borderColor: "rgba(255,255,255,0.05)",
            }}
          >
            <button
              onClick={() => setSidebarOpen((v) => !v)}
              aria-label="Toggle sidebar"
              className="p-2 rounded-xl hover:bg-white/5 text-zinc-500 hover:text-white transition-colors"
            >
              <Menu className="w-4 h-4" />
            </button>
            <div className="flex-1 min-w-0">
              <span className="text-sm font-medium text-zinc-400 truncate block">
                {view === "upload" ? "New Analysis" : selectedReport?.title ?? "Loading..."}
              </span>
            </div>
            {view === "report" && selectedReport && (
              <div className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border flex-shrink-0 ${riskMeta(selectedReport.risk_score).color} ${riskMeta(selectedReport.risk_score).bg} ${riskMeta(selectedReport.risk_score).border}`}>
                <div className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
                Risk {selectedReport.risk_score}/10
              </div>
            )}
          </div>

          {/* Scrollable content */}
          <div className="flex-1 overflow-y-auto custom-scrollbar">

            {/* ── UPLOAD VIEW ── */}
            {view === "upload" && (
              uploading ? (
                <AnalysisProgress active={uploading} />
              ) : (
                <div className="h-full flex flex-col items-center justify-center p-8">
                  <motion.div
                    initial={{ opacity: 0, scale: 0.97 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.35 }}
                    className="w-full max-w-2xl"
                  >
                    {/* Header */}
                    <div className="text-center mb-10">
                      <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold mb-5"
                        style={{ background: "rgba(14,165,233,0.1)", border: "1px solid rgba(14,165,233,0.2)", color: "#38BDF8" }}>
                        <div className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
                        AI-Powered Analysis
                        <Sparkles className="w-3 h-3" />
                      </div>
                      <h1 className="text-3xl font-display font-bold text-white mb-2">Upload a CBC Report</h1>
                      <p className="text-zinc-500 text-sm leading-relaxed max-w-md mx-auto">
                        AI will extract every parameter, assess clinical risk, and generate insights in minutes.
                      </p>
                    </div>

                    {/* Drop zone */}
                    <label
                      className="relative block cursor-pointer rounded-3xl p-1 transition-all duration-300"
                      style={{
                        background: file
                          ? "linear-gradient(135deg, rgba(6,214,160,0.15), rgba(6,214,160,0.04))"
                          : dragOver
                          ? "linear-gradient(135deg, rgba(14,165,233,0.18), rgba(14,165,233,0.06))"
                          : "linear-gradient(135deg, rgba(255,255,255,0.04), transparent)",
                      }}
                      onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                      onDragLeave={() => setDragOver(false)}
                      onDrop={handleDrop}
                    >
                      <div
                        className="relative rounded-[22px] p-14 flex flex-col items-center justify-center gap-5 min-h-[260px] transition-all duration-300"
                        style={{
                          background: file
                            ? "rgba(6,214,160,0.04)"
                            : "rgba(15,22,35,0.6)",
                          border: `2px dashed ${file ? "rgba(6,214,160,0.4)" : dragOver ? "rgba(14,165,233,0.5)" : "rgba(255,255,255,0.08)"}`,
                          backdropFilter: "blur(12px)",
                        }}
                      >
                        <input
                          type="file"
                          accept=".pdf,image/*"
                          className="hidden"
                          onChange={(e) => setFile(e.target.files?.[0] || null)}
                        />
                        {/* Icon */}
                        <div
                          className="p-5 rounded-2xl transition-all duration-300"
                          style={{
                            background: file
                              ? "rgba(6,214,160,0.15)"
                              : dragOver
                              ? "rgba(14,165,233,0.15)"
                              : "rgba(255,255,255,0.04)",
                            color: file ? "#06D6A0" : dragOver ? "#38BDF8" : "#52525b",
                          }}
                        >
                          {file ? <CheckCircle size={36} /> : <Upload size={36} />}
                        </div>
                        <div className="text-center">
                          <div className="text-lg font-display font-bold text-white mb-1">
                            {file ? "File Ready" : "Drop your report here"}
                          </div>
                          <p className="text-sm text-zinc-500">
                            {file ? file.name : "PDF or image · CBC, blood panel, lab report"}
                          </p>
                          {!file && (
                            <p className="text-xs text-zinc-600 mt-2">or click to browse</p>
                          )}
                        </div>
                      </div>
                    </label>

                    {file && (
                      <motion.div
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="mt-4 flex gap-3"
                      >
                        <button
                          onClick={() => setFile(null)}
                          className="px-5 py-3 rounded-xl text-zinc-400 hover:text-white transition-colors text-sm"
                          style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}
                        >
                          Clear
                        </button>
                        <button
                          onClick={handleAnalysis}
                          disabled={uploading}
                          className="flex-1 flex items-center justify-center gap-2 py-3 rounded-xl text-white font-semibold text-sm transition-all duration-200 disabled:opacity-50"
                          style={{
                            background: "linear-gradient(135deg, #0EA5E9, #0284C7)",
                            boxShadow: "0 4px 24px rgba(14,165,233,0.3)",
                          }}
                        >
                          <Sparkles className="w-4 h-4" />
                          Run Analysis
                        </button>
                      </motion.div>
                    )}

                    {!file && (
                      <div className="mt-8 grid grid-cols-3 gap-4">
                        {[
                          { icon: <Activity className="w-5 h-5 text-primary" />,    label: "Instant Analysis", sub: "AI-powered extraction" },
                          { icon: <ShieldAlert className="w-5 h-5 text-accent" />,  label: "Risk Detection",   sub: "Identify health risks" },
                          { icon: <Sparkles className="w-5 h-5 text-yellow-400" />, label: "RAG Chatbot",      sub: "Ask about your report" },
                        ].map((f) => (
                          <div
                            key={f.label}
                            className="p-4 rounded-2xl text-center hover:border-white/10 transition-colors"
                            style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)" }}
                          >
                            <div className="flex justify-center mb-2">{f.icon}</div>
                            <div className="text-sm font-display font-bold text-white">{f.label}</div>
                            <div className="text-xs text-zinc-600 mt-1">{f.sub}</div>
                          </div>
                        ))}
                      </div>
                    )}
                  </motion.div>
                </div>
              )
            )}

            {/* ── REPORT VIEW ── */}
            {view === "report" && (
              <div className="px-6 py-8 md:px-10">
                {loadingReport ? (
                  <div className="h-[60vh] flex flex-col items-center justify-center gap-5">
                    <div className="relative w-20 h-20">
                      <div className="absolute inset-0 rounded-full border-t-2 border-b-2 border-primary animate-spin" />
                      <div className="absolute inset-3 rounded-full border-t border-primary/40 animate-spin" style={{ animationDirection: "reverse", animationDuration: "1.5s" }} />
                      <div className="absolute inset-0 flex items-center justify-center">
                        <Sparkles className="w-5 h-5 text-primary animate-pulse" />
                      </div>
                    </div>
                    <div className="text-center">
                      <p className="text-zinc-300 text-sm font-medium">Loading report...</p>
                      <p className="text-zinc-600 text-xs mt-1 font-mono">Fetching clinical data</p>
                    </div>
                  </div>
                ) : selectedReport ? (
                  <motion.div
                    key={selectedReport.id}
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.35 }}
                    className="max-w-5xl mx-auto space-y-6 pb-20"
                  >
                    {/* ── Report Header ── */}
                    <div className="flex flex-col md:flex-row items-start md:items-end justify-between gap-5 pb-6 border-b border-white/5">
                      <div>
                        <div className="flex items-center flex-wrap gap-2 mb-2">
                          <span className="px-3 py-1 rounded-full text-primary text-xs font-bold uppercase tracking-wider"
                            style={{ background: "rgba(14,165,233,0.1)", border: "1px solid rgba(14,165,233,0.2)" }}>
                            CBC Report
                          </span>
                          <span className="text-zinc-600 text-xs flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {new Date(selectedReport.created_at).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })}
                          </span>
                        </div>
                        <h1 className="text-2xl md:text-3xl font-display font-bold text-white leading-tight">{selectedReport.title}</h1>
                        <div className="flex items-center gap-2 mt-2 text-zinc-500">
                          <FileText className="w-3.5 h-3.5" />
                          <span className="font-mono text-xs">{selectedReport.filename}</span>
                        </div>
                      </div>

                      {/* Risk score badge */}
                      {(() => {
                        const rm = riskMeta(selectedReport.risk_score);
                        return (
                          <div
                            className={`flex items-center gap-4 px-6 py-4 rounded-2xl backdrop-blur-sm flex-shrink-0 ${rm.bg} ${rm.border} border`}
                          >
                            <div className="text-right">
                              <div className={`text-[10px] font-bold uppercase tracking-widest ${rm.color} opacity-70 font-mono`}>Risk Score</div>
                              <div className={`text-4xl font-display font-bold tabular-nums ${rm.color}`}>{selectedReport.risk_score}<span className="text-lg opacity-50">/10</span></div>
                              <div className={`text-xs ${rm.color} opacity-60`}>{rm.label} Risk</div>
                            </div>
                            <div className={`p-2 rounded-xl ${rm.bg}`}>
                              <Activity className={`w-7 h-7 ${rm.color}`} />
                            </div>
                          </div>
                        );
                      })()}
                    </div>

                    {/* ── Tab Bar ── */}
                    <div
                      className="flex gap-1 p-1 rounded-2xl w-fit"
                      style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}
                    >
                      {(["overview", "chart", "chat"] as const).map((tab) => {
                        const meta = {
                          overview: { label: "Overview", icon: <FileText className="w-3.5 h-3.5" /> },
                          chart:    { label: "CBC Chart", icon: <BarChart2 className="w-3.5 h-3.5" /> },
                          chat:     { label: "AI Chat",   icon: <Sparkles className="w-3.5 h-3.5" /> },
                        };
                        const active = reportTab === tab;
                        return (
                          <button
                            key={tab}
                            onClick={() => setReportTab(tab)}
                            className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200"
                            style={{
                              background: active ? "linear-gradient(135deg, rgba(14,165,233,0.2), rgba(14,165,233,0.08))" : "transparent",
                              border: active ? "1px solid rgba(14,165,233,0.25)" : "1px solid transparent",
                              color: active ? "#38BDF8" : "#71717a",
                            }}
                          >
                            {meta[tab].icon}
                            {meta[tab].label}
                          </button>
                        );
                      })}
                    </div>

                    {/* ── OVERVIEW TAB ── */}
                    {reportTab === "overview" && (
                      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.2 }} className="space-y-6">

                        {/* Parameters Grid */}
                        {selectedReport.param_interpretation && (
                          <div>
                            <h2 className="text-xs font-semibold text-zinc-500 mb-3 uppercase tracking-widest flex items-center gap-2">
                              <FlaskConical className="w-3.5 h-3.5 text-primary/60" />
                              CBC Parameters
                            </h2>
                            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                              {Object.entries(selectedReport.param_interpretation).map(([key, data]: [string, any], i) => (
                                <motion.div
                                  key={key}
                                  initial={{ opacity: 0, y: 8 }}
                                  animate={{ opacity: 1, y: 0 }}
                                  transition={{ duration: 0.3, delay: i * 0.04 }}
                                  whileHover={{ y: -3 }}
                                  className="p-4 rounded-2xl border transition-all duration-200 cursor-default group"
                                  style={{
                                    background: data.status === "high"
                                      ? "linear-gradient(135deg, rgba(239,68,68,0.06), rgba(239,68,68,0.02))"
                                      : data.status === "low"
                                      ? "linear-gradient(135deg, rgba(234,179,8,0.06), rgba(234,179,8,0.02))"
                                      : "linear-gradient(135deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01))",
                                    borderColor: data.status === "high"
                                      ? "rgba(239,68,68,0.18)"
                                      : data.status === "low"
                                      ? "rgba(234,179,8,0.18)"
                                      : "rgba(255,255,255,0.06)",
                                  }}
                                >
                                  <div className="flex justify-between items-start mb-2">
                                    <div className="text-xs font-medium text-zinc-400 truncate flex-1 mr-1 font-mono">{key}</div>
                                    <div className={`w-2 h-2 rounded-full flex-shrink-0 mt-0.5 ${
                                      data.status === "high"   ? "bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.8)]"
                                      : data.status === "low"  ? "bg-yellow-500 shadow-[0_0_6px_rgba(234,179,8,0.8)]"
                                      : "bg-emerald-500 shadow-[0_0_6px_rgba(34,197,94,0.7)]"}`}
                                    />
                                  </div>
                                  <div className="text-xl font-display font-bold text-white tabular-nums">
                                    {data.value} <span className="text-xs font-normal text-zinc-500">{data.unit}</span>
                                  </div>
                                  <div className="text-[10px] text-zinc-600 font-mono mt-1">
                                    ref: {data.reference?.low} – {data.reference?.high}
                                  </div>
                                </motion.div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Synthesis + Side cards */}
                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
                          {/* Clinical Synthesis */}
                          <div
                            className="lg:col-span-2 rounded-2xl p-7 relative overflow-hidden"
                            style={{
                              background: "linear-gradient(135deg, rgba(15,22,35,0.9), rgba(10,16,28,0.95))",
                              border: "1px solid rgba(14,165,233,0.1)",
                              boxShadow: "0 0 40px rgba(14,165,233,0.04)",
                            }}
                          >
                            <div className="absolute top-0 right-0 w-52 h-52 opacity-30 pointer-events-none"
                              style={{ background: "radial-gradient(circle at top right, rgba(14,165,233,0.12), transparent 70%)" }} />
                            <h3 className="text-sm font-display font-bold text-white mb-4 flex items-center gap-2 relative z-10">
                              <div className="p-1.5 bg-primary/15 rounded-lg text-primary border border-primary/20">
                                <FileText className="w-3.5 h-3.5" />
                              </div>
                              Clinical Synthesis
                            </h3>
                            <div className="relative z-10">
                              {Array.isArray(selectedReport.synthesis_report)
                                ? selectedReport.synthesis_report.map((block, idx) => <SafeMarkdown key={idx} content={block} />)
                                : <SafeMarkdown content={selectedReport.synthesis_report || ""} />}
                            </div>
                          </div>

                          {/* Side cards */}
                          <div className="space-y-4">
                            {/* Risk Assessment */}
                            <div
                              className="rounded-2xl p-5"
                              style={{
                                background: "linear-gradient(135deg, rgba(15,22,35,0.9), rgba(10,16,28,0.95))",
                                border: "1px solid rgba(255,255,255,0.06)",
                              }}
                            >
                              <h3 className="text-sm font-display font-bold text-white mb-3 flex items-center gap-2">
                                <ShieldAlert className="w-4 h-4 text-accent" />
                                Risk Assessment
                              </h3>
                              {Array.isArray(selectedReport.risk_rationale) ? (
                                <ul className="space-y-2">
                                  {selectedReport.risk_rationale.map((r, i) => (
                                    <li key={i} className="flex gap-2 text-xs text-zinc-400">
                                      <span className="text-accent mt-0.5 flex-shrink-0">›</span>
                                      <span>{r}</span>
                                    </li>
                                  ))}
                                </ul>
                              ) : (
                                <p className="text-xs text-zinc-400 leading-relaxed">{selectedReport.risk_rationale || "No specific risk rationale."}</p>
                              )}
                            </div>

                            {/* Patterns */}
                            <div
                              className="rounded-2xl p-5"
                              style={{
                                background: "linear-gradient(135deg, rgba(15,22,35,0.9), rgba(10,16,28,0.95))",
                                border: "1px solid rgba(255,255,255,0.06)",
                              }}
                            >
                              <h3 className="text-sm font-display font-bold text-white mb-3 flex items-center gap-2">
                                <Activity className="w-4 h-4 text-primary" />
                                Patterns Detected
                              </h3>
                              <div className="flex flex-wrap gap-2">
                                {selectedReport.patterns?.length > 0 ? (
                                  selectedReport.patterns.map((pat, i) => (
                                    <span
                                      key={i}
                                      className="px-2.5 py-1 rounded-lg text-xs text-zinc-300"
                                      style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.07)" }}
                                    >
                                      {pat}
                                    </span>
                                  ))
                                ) : (
                                  <span className="text-zinc-600 text-xs italic">No specific patterns detected.</span>
                                )}
                              </div>
                            </div>
                          </div>
                        </div>

                        {/* Recommendations */}
                        {selectedReport.recommendations?.length > 0 && (
                          <div
                            className="rounded-2xl p-7"
                            style={{
                              background: "linear-gradient(135deg, rgba(15,22,35,0.9), rgba(10,16,28,0.95))",
                              border: "1px solid rgba(6,214,160,0.1)",
                            }}
                          >
                            <h3 className="text-sm font-display font-bold text-white mb-4 flex items-center gap-2">
                              <div className="p-1.5 bg-accent/15 rounded-lg text-accent border border-accent/20">
                                <CheckCircle className="w-3.5 h-3.5" />
                              </div>
                              Recommendations
                            </h3>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                              {selectedReport.recommendations.map((rec, i) => (
                                <div
                                  key={i}
                                  className="flex gap-3 p-4 rounded-xl transition-colors hover:border-accent/15"
                                  style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)" }}
                                >
                                  <Check className="w-4 h-4 text-accent flex-shrink-0 mt-0.5" />
                                  <span className="text-zinc-300 text-sm leading-relaxed">{rec}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </motion.div>
                    )}

                    {/* ── CHART TAB ── */}
                    {reportTab === "chart" && (
                      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.2 }}>
                        {selectedReport.param_interpretation ? (
                          <div
                            className="rounded-2xl p-7"
                            style={{
                              background: "linear-gradient(135deg, rgba(15,22,35,0.9), rgba(10,16,28,0.95))",
                              border: "1px solid rgba(14,165,233,0.1)",
                            }}
                          >
                            <h3 className="text-sm font-display font-bold text-white mb-1 flex items-center gap-2">
                              <div className="p-1.5 bg-primary/15 rounded-lg text-primary border border-primary/20">
                                <BarChart2 className="w-3.5 h-3.5" />
                              </div>
                              CBC Parameter Chart
                            </h3>
                            <p className="text-xs text-zinc-500 mb-6 ml-9">Values as % of reference midpoint. Green = normal · Yellow = low · Red = high.</p>
                            <CbcChart data={selectedReport.param_interpretation} />
                          </div>
                        ) : (
                          <div className="rounded-2xl p-10 text-center" style={{ background: "rgba(15,22,35,0.8)", border: "1px solid rgba(255,255,255,0.05)" }}>
                            <BarChart2 className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
                            <p className="text-zinc-500 text-sm">No parameter data available.</p>
                          </div>
                        )}
                      </motion.div>
                    )}

                    {/* ── CHAT TAB ── */}
                    {reportTab === "chat" && (
                      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.2 }}>
                        {selectedReport.rag_collection_name ? (
                          <div
                            className="rounded-2xl overflow-hidden"
                            style={{
                              background: "linear-gradient(135deg, rgba(15,22,35,0.9), rgba(10,16,28,0.95))",
                              border: "1px solid rgba(139,92,246,0.12)",
                            }}
                          >
                            <div className="p-5 border-b flex items-center justify-between" style={{ borderColor: "rgba(255,255,255,0.06)", background: "rgba(255,255,255,0.02)" }}>
                              <div>
                                <h3 className="text-sm font-display font-bold text-white flex items-center gap-2">
                                  <Sparkles className="w-4 h-4 text-violet-400" />
                                  Ask AI about this report
                                </h3>
                                <p className="text-xs text-zinc-500 mt-0.5">Powered by RAG — answers grounded in your data</p>
                              </div>
                              <div className="flex items-center gap-1.5">
                                <div className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
                                <span className="text-[10px] text-accent font-mono">LIVE</span>
                              </div>
                            </div>
                            <ChatComponent collectionName={selectedReport.rag_collection_name} sessionId={sessionId} />
                          </div>
                        ) : (
                          <div className="rounded-2xl p-10 text-center" style={{ background: "rgba(15,22,35,0.8)", border: "1px solid rgba(255,255,255,0.05)" }}>
                            <Sparkles className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
                            <p className="text-zinc-500 text-sm">AI chat is not available for this report.</p>
                          </div>
                        )}
                      </motion.div>
                    )}
                  </motion.div>
                ) : null}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── DELETE CONFIRM MODAL ── */}
      <ConfirmModal
        open={confirmDelete !== null}
        title="Delete Report?"
        description="This will permanently delete the report and its AI knowledge base. This action cannot be undone."
        confirmLabel="Delete"
        onConfirm={handleDeleteReport}
        onCancel={() => setConfirmDelete(null)}
      />

      {/* ── SETTINGS DRAWER ── */}
      <AnimatePresence>
        {showSettings && (
          <>
            <motion.div
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm"
              onClick={() => setShowSettings(false)}
              aria-hidden="true"
            />
            <motion.div
              initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }}
              transition={{ type: "spring", damping: 28, stiffness: 220 }}
              className="fixed top-0 right-0 z-50 h-full w-full max-w-sm flex flex-col shadow-2xl"
              style={{
                background: "linear-gradient(180deg, rgba(15,22,35,0.98) 0%, rgba(10,16,28,1) 100%)",
                border: "1px solid rgba(255,255,255,0.07)",
                borderRight: "none",
                backdropFilter: "blur(24px)",
              }}
              role="dialog"
              aria-label="Settings"
            >
              <div className="p-6 border-b flex items-center justify-between flex-shrink-0" style={{ borderColor: "rgba(255,255,255,0.06)" }}>
                <h2 className="text-base font-display font-bold text-white">Settings</h2>
                <button
                  onClick={() => setShowSettings(false)}
                  aria-label="Close settings"
                  className="p-2 hover:bg-white/5 rounded-xl transition-colors text-zinc-400 hover:text-white"
                >
                  <X size={16} />
                </button>
              </div>

              <div className="flex-1 p-6 overflow-y-auto custom-scrollbar space-y-5">
                {/* Avatar */}
                <div className="flex flex-col items-center pb-5 border-b" style={{ borderColor: "rgba(255,255,255,0.06)" }}>
                  <div className="w-20 h-20 rounded-full mb-4 overflow-hidden relative group"
                    style={{ border: "2px solid rgba(14,165,233,0.2)" }}>
                    {clerkUser?.imageUrl ? (
                      <img src={clerkUser.imageUrl} alt="Profile" className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-primary to-primaryDark text-2xl font-display font-bold text-white">
                        {(clerkUser?.fullName || "?")[0].toUpperCase()}
                      </div>
                    )}
                    {isEditing && (
                      <label className="absolute inset-0 bg-black/60 flex items-center justify-center cursor-pointer opacity-0 group-hover:opacity-100 transition-opacity">
                        <Camera className="text-white w-5 h-5" />
                        <input type="file" accept="image/*" onChange={handlePhotoUpload} className="hidden" />
                      </label>
                    )}
                  </div>

                  {!isEditing ? (
                    <div className="text-center">
                      <h3 className="text-base font-display font-bold text-white">{clerkUser?.fullName || "User"}</h3>
                      <p className="text-zinc-500 text-sm mt-0.5">{userEmail}</p>
                      <button
                        onClick={() => setIsEditing(true)}
                        className="mt-3 flex items-center gap-1.5 text-primary text-xs hover:text-primaryGlow transition-colors mx-auto"
                      >
                        <Edit2 className="w-3 h-3" /> Edit Profile
                      </button>
                    </div>
                  ) : (
                    <form onSubmit={handleUpdateProfile} className="w-full space-y-3 mt-2">
                      <div>
                        <label htmlFor="display-name" className="text-xs font-semibold text-zinc-500 uppercase tracking-wider block mb-1.5">Display Name</label>
                        <input
                          id="display-name" type="text" value={userName}
                          onChange={(e) => setUserName(e.target.value)}
                          className="glass-input w-full" placeholder="Your name"
                        />
                      </div>
                      <div className="flex gap-2">
                        <button type="button" onClick={() => setIsEditing(false)}
                          className="flex-1 py-2.5 rounded-xl text-sm font-medium text-zinc-400 hover:text-white transition-colors"
                          style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
                          Cancel
                        </button>
                        <button type="submit" disabled={updatingProfile}
                          className="flex-1 py-2.5 rounded-xl text-sm font-semibold text-white disabled:opacity-50 transition-all"
                          style={{ background: "linear-gradient(135deg, #0EA5E9, #0284C7)" }}>
                          {updatingProfile ? "Saving…" : "Save"}
                        </button>
                      </div>
                    </form>
                  )}
                </div>

                {/* Account info */}
                <div className="rounded-2xl p-4" style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)" }}>
                  <p className="text-[10px] text-zinc-500 uppercase font-semibold tracking-widest mb-3">Account</p>
                  <p className="text-sm text-zinc-200 font-medium">{clerkUser?.fullName}</p>
                  <p className="text-xs text-zinc-500 mt-0.5">{userEmail}</p>
                </div>

                {/* Activity */}
                <div className="rounded-2xl p-4" style={{ background: "rgba(14,165,233,0.04)", border: "1px solid rgba(14,165,233,0.1)" }}>
                  <p className="text-[10px] text-zinc-500 uppercase font-semibold tracking-widest mb-3">Activity</p>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-zinc-400">Reports analyzed</span>
                    <span className="font-display font-bold text-primary tabular-nums text-lg">{reports.length}</span>
                  </div>
                </div>

                {/* Sign out */}
                <div className="pt-2">
                  <button
                    onClick={() => signOut({ redirectUrl: "/sign-in" })}
                    className="w-full py-3 rounded-2xl font-medium text-red-400 text-sm flex items-center justify-center gap-2 transition-all hover:brightness-110"
                    style={{ background: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.15)" }}
                  >
                    <LogOut size={14} />
                    Sign Out
                  </button>
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
