"use client";

import { useState, useEffect, useCallback } from "react";
import { v4 as uuidv4 } from "uuid";
import { useUser, useClerk } from "@clerk/nextjs";
import axios from "axios";
import {
  LogOut, Upload, AlertCircle, CheckCircle, Clock,
  FileText, Settings, User, Camera, X, Loader2,
  Edit2, Save, PlusCircle, FileSearch,
  Check, ShieldAlert, Activity, Sparkles, BrainCircuit,
  Trash2, ChevronRight, Menu,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import ChatComponent from "./ChatComponent";

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
    Today: [],
    Yesterday: [],
    "Last 7 Days": [],
    "Last 30 Days": [],
    Older: [],
  };

  for (const r of reports) {
    const d = new Date(r.created_at);
    const ds = d.toDateString();
    if (ds === today) groups["Today"].push(r);
    else if (ds === yesterday) groups["Yesterday"].push(r);
    else if (d >= week) groups["Last 7 Days"].push(r);
    else if (d >= month) groups["Last 30 Days"].push(r);
    else groups["Older"].push(r);
  }

  return groups;
}

function riskColor(score: number) {
  if (score > 6) return "text-red-400 bg-red-500/10 border-red-500/20";
  if (score > 3) return "text-yellow-400 bg-yellow-500/10 border-yellow-500/20";
  return "text-green-400 bg-green-500/10 border-green-500/20";
}

// ─── Component ───────────────────────────────────────────────────────────────

export default function Dashboard() {
  const { user: clerkUser } = useUser();
  const { signOut } = useClerk();

  const userId = clerkUser?.id || "";
  const userEmail = clerkUser?.primaryEmailAddress?.emailAddress || "";

  // View
  const [view, setView] = useState<"upload" | "report">("upload");
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // Reports
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [selectedReport, setSelectedReport] = useState<ReportDetail | null>(null);
  const [loadingReports, setLoadingReports] = useState(true);
  const [loadingReport, setLoadingReport] = useState(false);
  const [activeReportId, setActiveReportId] = useState<string | null>(null);

  // Upload
  const [uploading, setUploading] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [sessionId, setSessionId] = useState(() => uuidv4());

  // Settings
  const [showSettings, setShowSettings] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [userName, setUserName] = useState(clerkUser?.fullName || "");
  const [userPhoto, setUserPhoto] = useState(clerkUser?.imageUrl || "");
  const [updatingProfile, setUpdatingProfile] = useState(false);

  // ─── Data Fetching ─────────────────────────────────────────────────────────

  const fetchReports = useCallback(async () => {
    setLoadingReports(true);
    try {
      const res = await axios.get<ReportSummary[]>("/api/reports");
      setReports(res.data);
    } catch (e) {
      console.error("Failed to fetch reports", e);
    } finally {
      setLoadingReports(false);
    }
  }, []);

  useEffect(() => {
    fetchReports();
  }, [fetchReports]);

  // ─── Actions ───────────────────────────────────────────────────────────────

  const handleNewAnalysis = () => {
    setView("upload");
    setSelectedReport(null);
    setActiveReportId(null);
    setFile(null);
    setSessionId(uuidv4());
  };

  const handleSelectReport = async (id: string) => {
    if (id === activeReportId) return;
    setActiveReportId(id);
    setLoadingReport(true);
    setView("report");
    try {
      const res = await axios.get<ReportDetail>(`/api/reports/${id}`);
      setSelectedReport(res.data);
      setSessionId(uuidv4());
    } catch (e) {
      console.error("Failed to load report", e);
    } finally {
      setLoadingReport(false);
    }
  };

  const handleDeleteReport = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm("Delete this report permanently?")) return;
    try {
      await axios.delete(`/api/reports/${id}`);
      setReports((prev) => prev.filter((r) => r.id !== id));
      if (activeReportId === id) {
        setSelectedReport(null);
        setActiveReportId(null);
        setView("upload");
      }
    } catch (e) {
      console.error("Failed to delete report", e);
    }
  };

  const handleAnalysis = async () => {
    if (!file) return;
    setUploading(true);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("session_id", sessionId);

    try {
      const response = await axios.post<ReportDetail>("/api/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 300000,
      });

      const data = response.data;

      if (data.errors && data.errors.length > 0) {
        alert("Analysis issues:\n" + data.errors.join("\n"));
      }

      setSelectedReport(data);
      setActiveReportId(data.id ?? null);
      setView("report");
      setFile(null);

      if (data.id) {
        const summary: ReportSummary = {
          id: data.id,
          filename: data.filename,
          title: data.title,
          risk_score: data.risk_score,
          created_at: data.created_at ?? new Date().toISOString(),
        };
        setReports((prev) => [summary, ...prev]);
      }
    } catch (error: any) {
      console.error("Upload failed:", error);
      let msg = "Analysis Failed!\n";
      if (error.response) {
        msg += `Server Error: ${error.response.status} — ${JSON.stringify(error.response.data)}`;
      } else if (error.request) {
        msg += "No response from server. Is the backend running?";
      } else {
        msg += error.message;
      }
      alert(msg);
    } finally {
      setUploading(false);
    }
  };

  const handleUpdateProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setUpdatingProfile(true);
    try {
      await clerkUser?.update({ firstName: userName });
      setIsEditing(false);
    } catch (error: any) {
      alert("Failed to update profile: " + error.message);
    } finally {
      setUpdatingProfile(false);
    }
  };

  const handlePhotoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) {
      const reader = new FileReader();
      reader.onloadend = () => setUserPhoto(reader.result as string);
      reader.readAsDataURL(f);
    }
  };

  // ─── Render ────────────────────────────────────────────────────────────────

  const groups = groupByDate(reports);

  return (
    <div className="min-h-screen bg-background text-white font-sans selection:bg-primary/30 relative overflow-hidden">
      {/* Ambient */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <div className="absolute top-[-20%] left-[-10%] w-[800px] h-[800px] bg-primary/10 rounded-full blur-[150px]" />
        <div className="absolute bottom-[-20%] right-[-10%] w-[800px] h-[800px] bg-accent/5 rounded-full blur-[150px]" />
      </div>

      <div className="relative z-10 w-full h-screen flex overflow-hidden">

        {/* ── LEFT SIDEBAR ──────────────────────────────────────────────── */}
        <AnimatePresence initial={false}>
          {sidebarOpen && (
            <motion.aside
              key="sidebar"
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 280, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="flex-shrink-0 h-full bg-surface/40 backdrop-blur-md border-r border-white/5 flex flex-col overflow-hidden"
              style={{ width: 280 }}
            >
              {/* Logo */}
              <div className="p-5 border-b border-white/5">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-primary/20 rounded-lg">
                    <BrainCircuit className="text-primary w-5 h-5" />
                  </div>
                  <span className="text-lg font-display font-bold text-white tracking-tight">Health AI</span>
                </div>
              </div>

              {/* New Analysis */}
              <div className="p-3">
                <button
                  onClick={handleNewAnalysis}
                  className="w-full flex items-center gap-2 px-4 py-2.5 rounded-xl bg-primary/10 hover:bg-primary/20 border border-primary/20 text-primary text-sm font-medium transition-all duration-200"
                >
                  <PlusCircle className="w-4 h-4" />
                  New Analysis
                </button>
              </div>

              {/* History List */}
              <div className="flex-1 overflow-y-auto custom-scrollbar px-2 pb-2">
                {loadingReports ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="w-5 h-5 animate-spin text-zinc-500" />
                  </div>
                ) : reports.length === 0 ? (
                  <div className="text-center py-8 px-4">
                    <FileSearch className="w-8 h-8 text-zinc-600 mx-auto mb-2" />
                    <p className="text-xs text-zinc-500">No reports yet. Upload your first CBC report.</p>
                  </div>
                ) : (
                  Object.entries(groups).map(([label, items]) =>
                    items.length === 0 ? null : (
                      <div key={label} className="mb-2">
                        <p className="text-[11px] font-semibold text-zinc-500 uppercase tracking-wider px-3 py-2">
                          {label}
                        </p>
                        {items.map((report) => (
                          <div
                            key={report.id}
                            onClick={() => handleSelectReport(report.id)}
                            className={`group relative flex flex-col gap-1 px-3 py-2.5 rounded-xl cursor-pointer transition-all duration-150 mb-0.5
                              ${activeReportId === report.id
                                ? "bg-primary/15 border border-primary/20"
                                : "hover:bg-white/5 border border-transparent"
                              }`}
                          >
                            <div className="flex items-start justify-between gap-2">
                              <p className="text-sm text-white font-medium leading-tight truncate flex-1">
                                {report.title}
                              </p>
                              <button
                                onClick={(e) => handleDeleteReport(report.id, e)}
                                className="opacity-0 group-hover:opacity-100 p-1 rounded-md hover:bg-error/20 hover:text-error text-zinc-500 transition-all flex-shrink-0"
                              >
                                <Trash2 className="w-3 h-3" />
                              </button>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-[11px] text-zinc-500 font-mono truncate flex-1">
                                {report.filename}
                              </span>
                              <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border flex-shrink-0 ${riskColor(report.risk_score)}`}>
                                {report.risk_score}/10
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )
                  )
                )}
              </div>

              {/* User Profile */}
              <div className="p-3 border-t border-white/5">
                <div
                  className="flex items-center gap-3 px-3 py-2 rounded-xl hover:bg-white/5 cursor-pointer transition-colors group"
                  onClick={() => setShowSettings(true)}
                >
                  <div className="w-8 h-8 rounded-full bg-zinc-800 border border-white/10 overflow-hidden flex-shrink-0">
                    {userPhoto ? (
                      <img src={userPhoto} alt="User" className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-primary to-primaryDark text-white text-sm font-bold">
                        {(clerkUser?.fullName || "U")[0].toUpperCase()}
                      </div>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-white truncate group-hover:text-primary transition-colors">
                      {clerkUser?.fullName || "User"}
                    </p>
                    <p className="text-[11px] text-zinc-500 truncate">{userEmail}</p>
                  </div>
                  <Settings className="w-4 h-4 text-zinc-600 group-hover:text-white transition-colors flex-shrink-0" />
                </div>
              </div>
            </motion.aside>
          )}
        </AnimatePresence>

        {/* ── MAIN CONTENT ──────────────────────────────────────────────── */}
        <div className="flex-1 flex flex-col h-full overflow-hidden">
          {/* Top bar */}
          <div className="flex items-center gap-3 px-4 py-3 border-b border-white/5 bg-background/30 backdrop-blur-sm flex-shrink-0">
            <button
              onClick={() => setSidebarOpen((v) => !v)}
              className="p-2 rounded-lg hover:bg-white/5 text-zinc-400 hover:text-white transition-colors"
            >
              <Menu className="w-4 h-4" />
            </button>
            <span className="text-sm text-zinc-500">
              {view === "upload"
                ? "New Analysis"
                : selectedReport?.title ?? "Loading..."}
            </span>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto">

            {/* ── UPLOAD VIEW ─────────────────────────────────────────── */}
            {view === "upload" && (
              <div className="h-full flex flex-col items-center justify-center p-8">
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="w-full max-w-xl"
                >
                  <div className="text-center mb-8">
                    <h1 className="text-3xl font-display font-bold text-white mb-2">
                      Upload a CBC Report
                    </h1>
                    <p className="text-zinc-500 text-sm">
                      AI will extract parameters, assess risks, and generate clinical insights.
                    </p>
                  </div>

                  <label className={`
                    relative block cursor-pointer group rounded-3xl p-1 transition-all duration-300
                    ${file
                      ? "bg-gradient-to-b from-green-500/20 to-green-500/5"
                      : "bg-gradient-to-b from-white/10 to-transparent hover:from-primary/20 hover:to-primary/5"}
                  `}>
                    <div className={`
                      relative bg-surface/50 backdrop-blur-sm border-2 border-dashed
                      ${file ? "border-green-500/50" : "border-white/10 group-hover:border-primary/40"}
                      rounded-[20px] p-12 transition-all duration-300
                      flex flex-col items-center justify-center gap-6 min-h-[280px]
                    `}>
                      <input
                        type="file"
                        accept=".pdf,image/*"
                        className="hidden"
                        onChange={(e) => setFile(e.target.files?.[0] || null)}
                      />
                      <div className={`p-5 rounded-full transition-all duration-300
                        ${file
                          ? "bg-green-500/20 text-green-400"
                          : "bg-white/5 text-zinc-400 group-hover:scale-110 group-hover:text-primary group-hover:bg-primary/10"
                        }`}>
                        {file ? <CheckCircle size={40} /> : <Upload size={40} />}
                      </div>
                      <div className="text-center">
                        <div className="text-xl font-bold text-white mb-1">
                          {file ? "File Ready" : "Drop your report here"}
                        </div>
                        <p className="text-sm text-zinc-500">
                          {file ? file.name : "PDF or image · CBC, blood panel, lab report"}
                        </p>
                      </div>
                    </div>
                  </label>

                  {file && (
                    <motion.div
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="mt-4 flex gap-3"
                    >
                      <button
                        onClick={() => setFile(null)}
                        className="px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-zinc-400 hover:text-white transition-colors text-sm"
                      >
                        Clear
                      </button>
                      <button
                        onClick={handleAnalysis}
                        disabled={uploading}
                        className="flex-1 btn-primary flex items-center justify-center gap-2 shadow-xl shadow-primary/20"
                      >
                        {uploading ? (
                          <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            Analyzing...
                          </>
                        ) : (
                          <>
                            <Sparkles className="w-4 h-4" />
                            Run Analysis
                          </>
                        )}
                      </button>
                    </motion.div>
                  )}

                  {!file && (
                    <div className="mt-8 grid grid-cols-3 gap-4">
                      {[
                        { icon: <Activity className="w-5 h-5 text-primary" />, label: "Instant Analysis", sub: "AI-powered extraction" },
                        { icon: <ShieldAlert className="w-5 h-5 text-accent" />, label: "Risk Detection", sub: "Identify health risks" },
                        { icon: <Sparkles className="w-5 h-5 text-yellow-400" />, label: "RAG Chatbot", sub: "Ask about your report" },
                      ].map((f) => (
                        <div key={f.label} className="p-4 rounded-2xl bg-white/5 border border-white/5 text-center">
                          <div className="flex justify-center mb-2">{f.icon}</div>
                          <div className="text-sm font-bold text-white">{f.label}</div>
                          <div className="text-xs text-zinc-500 mt-1">{f.sub}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </motion.div>
              </div>
            )}

            {/* ── REPORT VIEW ─────────────────────────────────────────── */}
            {view === "report" && (
              <div className="px-6 py-8 md:px-12">
                {loadingReport ? (
                  <div className="h-[60vh] flex flex-col items-center justify-center">
                    <div className="relative">
                      <div className="w-20 h-20 rounded-full border-t-2 border-b-2 border-primary animate-spin" />
                      <div className="absolute inset-0 flex items-center justify-center">
                        <Sparkles className="w-7 h-7 text-primary animate-pulse" />
                      </div>
                    </div>
                    <p className="mt-6 text-zinc-400 text-sm">Loading report...</p>
                  </div>
                ) : selectedReport ? (
                  <motion.div
                    key={selectedReport.id}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.4 }}
                    className="max-w-5xl mx-auto space-y-8 pb-20"
                  >
                    {/* Report Header */}
                    <div className="flex flex-col md:flex-row items-end justify-between gap-6 border-b border-white/10 pb-8">
                      <div>
                        <div className="flex items-center gap-3 mb-2">
                          <span className="px-3 py-1 rounded-full bg-primary/10 border border-primary/20 text-primary text-xs font-bold uppercase tracking-wider">
                            Generated Report
                          </span>
                          <span className="text-zinc-500 text-sm flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {new Date(selectedReport.created_at).toLocaleDateString(undefined, {
                              year: "numeric", month: "short", day: "numeric",
                            })}
                          </span>
                        </div>
                        <h1 className="text-3xl md:text-4xl font-display font-bold text-white leading-tight">
                          {selectedReport.title}
                        </h1>
                        <div className="flex items-center gap-2 mt-3 text-zinc-400">
                          <FileText className="w-4 h-4" />
                          <span className="font-mono text-sm">{selectedReport.filename}</span>
                        </div>
                      </div>

                      <div className={`flex items-center gap-3 px-5 py-4 rounded-2xl border backdrop-blur-sm flex-shrink-0
                        ${selectedReport.risk_score > 6
                          ? "bg-error/10 border-error/20 text-error"
                          : selectedReport.risk_score > 3
                          ? "bg-warning/10 border-warning/20 text-warning"
                          : "bg-success/10 border-success/20 text-success"
                        }`}>
                        <div className="text-right">
                          <div className="text-xs font-bold uppercase tracking-wider opacity-80">Risk Score</div>
                          <div className="text-3xl font-display font-bold">{selectedReport.risk_score}/10</div>
                        </div>
                        <Activity className="w-8 h-8 opacity-80" />
                      </div>
                    </div>

                    {/* Parameters Grid */}
                    {selectedReport.param_interpretation && (
                      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                        {Object.entries(selectedReport.param_interpretation).map(([key, data]: [string, any]) => {
                          const isAbnormal = data.status !== "normal";
                          return (
                            <motion.div
                              key={key}
                              whileHover={{ y: -4 }}
                              className={`p-4 rounded-xl border transition-all duration-300
                                ${isAbnormal ? "bg-white/10 border-white/20" : "bg-white/5 border-white/5"}`}
                            >
                              <div className="flex justify-between items-start mb-2">
                                <div className="text-xs font-medium text-zinc-400">{key}</div>
                                <div className={`w-2 h-2 rounded-full flex-shrink-0
                                  ${data.status === "high" ? "bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.8)]"
                                  : data.status === "low" ? "bg-yellow-500 shadow-[0_0_8px_rgba(234,179,8,0.8)]"
                                  : "bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.8)]"}`}
                                />
                              </div>
                              <div className="text-xl font-bold text-white">
                                {data.value} <span className="text-xs font-normal text-zinc-500">{data.unit}</span>
                              </div>
                              <div className="text-[11px] text-zinc-600 font-mono mt-1">
                                Ref: {data.reference?.low} – {data.reference?.high}
                              </div>
                            </motion.div>
                          );
                        })}
                      </div>
                    )}

                    {/* Synthesis + Side Cards */}
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                      <div className="lg:col-span-2 glass-card rounded-3xl p-8 border-white/10 relative overflow-hidden">
                        <div className="absolute top-0 right-0 w-64 h-64 bg-primary/10 rounded-full blur-[80px] -mr-20 -mt-20 pointer-events-none" />
                        <h3 className="text-xl font-bold text-white mb-5 flex items-center gap-3 relative z-10">
                          <div className="p-2 bg-primary/20 rounded-lg text-primary"><FileText className="w-5 h-5" /></div>
                          Clinical Synthesis
                        </h3>
                        <div className="prose prose-invert prose-p:text-zinc-300 prose-strong:text-white max-w-none relative z-10">
                          {Array.isArray(selectedReport.synthesis_report) ? (
                            selectedReport.synthesis_report.map((block: string, idx: number) => (
                              <div
                                key={idx}
                                dangerouslySetInnerHTML={{
                                  __html: block
                                    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
                                    .replace(/\n/g, "<br />"),
                                }}
                                className="mb-4"
                              />
                            ))
                          ) : (
                            <div dangerouslySetInnerHTML={{
                              __html: (selectedReport.synthesis_report || "")
                                .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
                                .replace(/\n/g, "<br />"),
                            }} />
                          )}
                        </div>
                      </div>

                      <div className="space-y-4">
                        <div className="glass-card rounded-3xl p-6 border-white/10">
                          <h3 className="font-bold text-white mb-3 flex items-center gap-2">
                            <ShieldAlert className="w-5 h-5 text-accent" />
                            Risk Assessment
                          </h3>
                          <div className="text-sm text-zinc-300 leading-relaxed">
                            {Array.isArray(selectedReport.risk_rationale) ? (
                              <ul className="space-y-2">
                                {selectedReport.risk_rationale.map((r: string, i: number) => (
                                  <li key={i} className="flex gap-2">
                                    <span className="text-accent mt-1">•</span>{r}
                                  </li>
                                ))}
                              </ul>
                            ) : (
                              <p>{selectedReport.risk_rationale || "No specific risk rationale."}</p>
                            )}
                          </div>
                        </div>

                        <div className="glass-card rounded-3xl p-6 border-white/10">
                          <h3 className="font-bold text-white mb-3 flex items-center gap-2">
                            <Activity className="w-5 h-5 text-primary" />
                            Patterns Detected
                          </h3>
                          <div className="flex flex-wrap gap-2">
                            {selectedReport.patterns && selectedReport.patterns.length > 0 ? (
                              selectedReport.patterns.map((pat: string, i: number) => (
                                <span key={i} className="px-3 py-1 rounded-lg bg-surfaceHighlight border border-white/5 text-xs text-zinc-300">
                                  {pat}
                                </span>
                              ))
                            ) : (
                              <span className="text-zinc-500 text-sm italic">No specific patterns.</span>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Recommendations */}
                    {selectedReport.recommendations && selectedReport.recommendations.length > 0 && (
                      <div className="glass-card rounded-3xl p-8 border-white/10">
                        <h3 className="text-xl font-bold text-white mb-5 flex items-center gap-3">
                          <div className="p-2 bg-green-500/20 rounded-lg text-green-500">
                            <CheckCircle className="w-5 h-5" />
                          </div>
                          Recommendations
                        </h3>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                          {selectedReport.recommendations.map((rec: string, i: number) => (
                            <div key={i} className="flex gap-3 p-4 rounded-xl bg-white/5 border border-white/5 hover:bg-white/10 transition-colors">
                              <Check className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
                              <span className="text-zinc-300 text-sm leading-relaxed">{rec}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* AI Chat */}
                    {selectedReport.rag_collection_name && (
                      <div className="glass-card rounded-3xl overflow-hidden border-white/10">
                        <div className="p-6 border-b border-white/10 bg-white/5">
                          <h3 className="text-lg font-bold text-white flex items-center gap-2">
                            <Sparkles className="w-5 h-5 text-primary" />
                            Ask AI about this report
                          </h3>
                        </div>
                        <ChatComponent
                          collectionName={selectedReport.rag_collection_name}
                          sessionId={sessionId}
                        />
                      </div>
                    )}
                  </motion.div>
                ) : null}
              </div>
            )}

          </div>
        </div>
      </div>

      {/* ── SETTINGS DRAWER ──────────────────────────────────────────────── */}
      <AnimatePresence>
        {showSettings && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
              onClick={() => setShowSettings(false)}
            />
            <motion.div
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ type: "spring", damping: 25, stiffness: 200 }}
              className="fixed top-0 right-0 z-50 h-full w-full max-w-sm bg-surface border-l border-white/10 shadow-2xl flex flex-col"
            >
              <div className="p-6 border-b border-white/10 flex items-center justify-between">
                <h2 className="text-xl font-bold text-white">Settings</h2>
                <button onClick={() => setShowSettings(false)} className="p-2 hover:bg-white/10 rounded-full transition-colors">
                  <X size={20} />
                </button>
              </div>

              <div className="flex-1 p-6 overflow-y-auto">
                <div className="flex flex-col items-center mb-8">
                  <div className="w-24 h-24 rounded-full bg-zinc-800 mb-4 overflow-hidden relative group">
                    {userPhoto ? (
                      <img src={userPhoto} alt="Profile" className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center bg-zinc-700 text-2xl font-bold">
                        {(userName || "?")[0]}
                      </div>
                    )}
                    {isEditing && (
                      <label className="absolute inset-0 bg-black/50 flex items-center justify-center cursor-pointer opacity-0 group-hover:opacity-100 transition-opacity">
                        <Camera className="text-white" />
                        <input type="file" accept="image/*" onChange={handlePhotoUpload} className="hidden" />
                      </label>
                    )}
                  </div>

                  {!isEditing ? (
                    <>
                      <h3 className="text-xl font-bold text-white">{userName || "User"}</h3>
                      <p className="text-zinc-500 text-sm">{userEmail}</p>
                      <button onClick={() => setIsEditing(true)} className="mt-4 text-primary text-sm hover:underline">
                        Edit Profile
                      </button>
                    </>
                  ) : (
                    <form onSubmit={handleUpdateProfile} className="w-full space-y-4">
                      <div>
                        <label className="text-xs font-bold text-zinc-500 uppercase">Display Name</label>
                        <input
                          type="text"
                          value={userName}
                          onChange={(e) => setUserName(e.target.value)}
                          className="w-full glass-input mt-1"
                        />
                      </div>
                      <div className="flex gap-2">
                        <button type="button" onClick={() => setIsEditing(false)} className="flex-1 py-2 rounded-lg bg-zinc-800 text-sm font-medium">
                          Cancel
                        </button>
                        <button type="submit" disabled={updatingProfile} className="flex-1 py-2 rounded-lg bg-primary text-white text-sm font-medium">
                          {updatingProfile ? "Saving..." : "Save"}
                        </button>
                      </div>
                    </form>
                  )}
                </div>

                <div className="border-t border-white/10 pt-6">
                  <button
                    onClick={() => signOut({ redirectUrl: "/sign-in" })}
                    className="w-full py-3 rounded-xl bg-error/10 text-error font-medium hover:bg-error/20 transition-colors flex items-center justify-center gap-2"
                  >
                    <LogOut size={18} /> Sign Out
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
