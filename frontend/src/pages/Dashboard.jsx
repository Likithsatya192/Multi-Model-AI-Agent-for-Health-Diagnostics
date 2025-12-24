import { useState, useEffect } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { signOut, updateProfile } from 'firebase/auth';
import { auth } from '../firebase';
import axios from 'axios';
import {
    LogOut, Upload, AlertCircle, CheckCircle, Clock,
    FileText, Settings, User, Camera, X, Loader2,
    Edit2, ChevronRight, Save, PlusCircle, FileSearch,
    Check, ShieldAlert, Activity, Sparkles, BrainCircuit
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import ChatComponent from '../components/ChatComponent';

export default function Dashboard({ user }) {
    // State
    const [selectedReport, setSelectedReport] = useState(null);
    const [loading, setLoading] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [file, setFile] = useState(null);
    const [sessionId] = useState(uuidv4()); // Ensure unique session per load

    // Settings State
    const [showSettings, setShowSettings] = useState(false);
    const [isEditing, setIsEditing] = useState(false);
    const [userName, setUserName] = useState(user.displayName || '');
    const [userPhoto, setUserPhoto] = useState(() => {
        return localStorage.getItem(`user_photo_${user.uid}`) || user.photoURL || '';
    });
    const [updatingProfile, setUpdatingProfile] = useState(false);

    // Persist photo to localStorage whenever it changes
    useEffect(() => {
        if (userPhoto) {
            localStorage.setItem(`user_photo_${user.uid}`, userPhoto);
        }
    }, [userPhoto, user.uid]);

    // Handle File Upload for Analysis
    const handleAnalysis = async () => {
        if (!file) return;

        setSelectedReport(null);
        setUploading(true);
        setLoading(true);

        const formData = new FormData();
        formData.append("file", file);
        formData.append("session_id", sessionId);

        try {
            const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
            const response = await axios.post(`${API_BASE}/analyze`, formData, {
                headers: { "Content-Type": "multipart/form-data" },
                timeout: 300000 // 5 minute timeout
            });

            const analysisResult = response.data;

            if (analysisResult.errors && analysisResult.errors.length > 0) {
                alert("Analysis Issues Found:\n" + analysisResult.errors.join("\n"));
            }

            const reportTitle = analysisResult.analysis_type
                ? `${analysisResult.analysis_type.replace(/_/g, ' ')} Analysis`
                : "Comprehensive Medical Synthesis";

            const newReport = {
                timestamp: new Date(),
                filename: file.name,
                title: reportTitle,
                ...analysisResult
            };

            setSelectedReport(newReport);

        } catch (error) {
            console.error("Operation failed:", error);
            let msg = "Analysis Failed!\n";
            if (error.response) {
                msg += `Server Error: ${error.response.status} - ${JSON.stringify(error.response.data)}`;
            } else if (error.request) {
                msg += "No response from server. Is the backend running?";
            } else {
                msg += error.message;
            }
            alert(msg);
        } finally {
            setUploading(false);
            setLoading(false);
            setFile(null);
        }
    };

    const handleLogout = () => signOut(auth);

    const handlePhotoUpload = (e) => {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onloadend = () => {
                setUserPhoto(reader.result);
            };
            reader.readAsDataURL(file);
        }
    };

    const handleUpdateProfile = async (e) => {
        e.preventDefault();
        setUpdatingProfile(true);
        try {
            await updateProfile(auth.currentUser, {
                displayName: userName
            });
            setIsEditing(false);
        } catch (error) {
            console.error("Failed to update profile", error);
            alert("Failed to update profile: " + error.message);
        } finally {
            setUpdatingProfile(false);
        }
    };

    return (
        <div className="min-h-screen bg-background text-white font-sans selection:bg-primary/30 relative overflow-hidden">

            {/* Ambient Background */}
            <div className="fixed inset-0 pointer-events-none z-0">
                <div className="absolute top-[-20%] left-[-10%] w-[800px] h-[800px] bg-primary/10 rounded-full blur-[150px]" />
                <div className="absolute bottom-[-20%] right-[-10%] w-[800px] h-[800px] bg-accent/5 rounded-full blur-[150px]" />
            </div>

            {/* Content Container */}
            <div className="relative z-10 w-full h-screen flex flex-col md:flex-row overflow-hidden">

                {/* LEFT PANEL: Sidebar / Upload */}
                <div className="w-full md:w-[400px] lg:w-[450px] flex-shrink-0 bg-surface/30 backdrop-blur-md border-r border-white/5 flex flex-col h-full relative z-20">

                    {/* Header Area */}
                    <div className="p-8 pb-4">
                        <div className="flex items-center gap-3 mb-2">
                            <div className="p-2 bg-primary/20 rounded-lg">
                                <BrainCircuit className="text-primary w-6 h-6" />
                            </div>
                            <h1 className="text-2xl font-display font-bold text-white tracking-tight">Health AI</h1>
                        </div>
                        <p className="text-zinc-400 text-sm pl-1">Advanced Medical Analysis</p>
                    </div>

                    {/* User Profile Mini */}
                    <div className="px-8 py-4 border-b border-white/5">
                        <div className="flex items-center gap-4 group cursor-pointer" onClick={() => setShowSettings(true)}>
                            <div className="w-10 h-10 rounded-full bg-zinc-800 borderborder-white/10 overflow-hidden relative">
                                {userPhoto ? (
                                    <img src={userPhoto} alt="User" className="w-full h-full object-cover" />
                                ) : (
                                    <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-primary to-primaryDark text-white font-bold">
                                        {(user.displayName || "U")[0].toUpperCase()}
                                    </div>
                                )}
                            </div>
                            <div className="flex-1">
                                <div className="text-sm font-medium text-white group-hover:text-primary transition-colors">{user.displayName || "User"}</div>
                                <div className="text-xs text-zinc-500">View Settings</div>
                            </div>
                            <Settings className="w-4 h-4 text-zinc-600 group-hover:text-white transition-colors" />
                        </div>
                    </div>

                    {/* Upload Section */}
                    <div className="flex-1 p-8 overflow-y-auto custom-scrollbar flex flex-col justify-center">
                        <motion.div
                            initial={{ opacity: 0, scale: 0.95 }}
                            animate={{ opacity: 1, scale: 1 }}
                            transition={{ duration: 0.5 }}
                            className="w-full"
                        >
                            <label className={`
                                relative block cursor-pointer group rounded-3xl p-1
                                transition-all duration-300
                                ${file ? 'bg-gradient-to-b from-green-500/20 to-green-500/5' : 'bg-gradient-to-b from-white/10 to-transparent hover:from-primary/20 hover:to-primary/5'}
                            `}>
                                <div className={`
                                    relative bg-surface/50 backdrop-blur-sm border-2 border-dashed
                                    ${file ? 'border-green-500/50' : 'border-white/10 group-hover:border-primary/40'}
                                    rounded-[20px] p-10 transition-all duration-300
                                    flex flex-col items-center justify-center gap-6 h-[320px]
                                `}>
                                    <input
                                        type="file"
                                        accept=".pdf,image/*"
                                        className="hidden"
                                        onChange={(e) => setFile(e.target.files[0])}
                                    />

                                    <div className={`p-5 rounded-full ${file ? 'bg-green-500/20 text-green-400' : 'bg-white/5 text-zinc-400 group-hover:scale-110 group-hover:text-primary group-hover:bg-primary/10'} transition-all duration-300`}>
                                        {file ? <CheckCircle size={40} /> : <Upload size={40} />}
                                    </div>

                                    <div className="text-center space-y-2">
                                        <div className="text-xl font-bold text-white group-hover:text-primary transition-colors">
                                            {file ? "File Selected" : "Upload Report"}
                                        </div>
                                        <p className="text-sm text-zinc-500 px-4">
                                            {file ? file.name : "Drag & drop PDF or Image here, or click to browse"}
                                        </p>
                                    </div>

                                    {file && (
                                        <div className="absolute inset-x-0 bottom-0 p-6">
                                            <motion.button
                                                initial={{ opacity: 0, y: 10 }}
                                                animate={{ opacity: 1, y: 0 }}
                                                onClick={(e) => { e.preventDefault(); handleAnalysis(); }}
                                                className="w-full btn-primary flex items-center justify-center gap-2 shadow-xl shadow-primary/20"
                                            >
                                                <Sparkles className="w-4 h-4" />
                                                Run Analysis
                                            </motion.button>
                                        </div>
                                    )}
                                </div>
                            </label>

                            {!file && (
                                <div className="mt-8 grid grid-cols-2 gap-4">
                                    <div className="p-4 rounded-2xl bg-white/5 border border-white/5">
                                        <Activity className="w-6 h-6 text-primary mb-3" />
                                        <div className="text-sm font-bold text-white">Instant Analysis</div>
                                        <div className="text-xs text-zinc-500 mt-1">AI-powered medical data extraction</div>
                                    </div>
                                    <div className="p-4 rounded-2xl bg-white/5 border border-white/5">
                                        <ShieldAlert className="w-6 h-6 text-accent mb-3" />
                                        <div className="text-sm font-bold text-white">Risk Detection</div>
                                        <div className="text-xs text-zinc-500 mt-1">Identify potential health risks early</div>
                                    </div>
                                </div>
                            )}
                        </motion.div>
                    </div>
                </div>

                {/* RIGHT PANEL: Results Area */}
                <div className="flex-1 flex flex-col h-full relative overflow-hidden bg-background/50">

                    {/* Main Scrollable Content */}
                    <div className="flex-1 overflow-y-auto px-6 py-8 md:p-12 scroll-smooth">

                        {loading && (
                            <div className="h-full flex flex-col items-center justify-center">
                                <div className="relative">
                                    <div className="w-24 h-24 rounded-full border-t-2 border-b-2 border-primary animate-spin"></div>
                                    <div className="absolute inset-0 flex items-center justify-center">
                                        <Sparkles className="w-8 h-8 text-primary animate-pulse" />
                                    </div>
                                </div>
                                <h2 className="mt-8 text-2xl font-display font-bold text-white animate-pulse">Analyzing Documents</h2>
                                <p className="text-zinc-500 mt-2 text-center max-w-sm">
                                    Our AI engine is extracting parameters, identifying patterns, and generating clinical insights...
                                </p>
                            </div>
                        )}

                        {!loading && !selectedReport && (
                            <div className="h-full flex flex-col items-center justify-center text-center p-8">
                                <div className="w-32 h-32 rounded-full bg-white/5 flex items-center justify-center mb-8 border border-white/5">
                                    <FileSearch className="w-12 h-12 text-zinc-600" />
                                </div>
                                <h2 className="text-3xl font-display font-bold text-white mb-4">No Report Selected</h2>
                                <p className="text-zinc-500 max-w-md mx-auto">
                                    Upload a medical document in the sidebar to generate a comprehensive health analysis.
                                </p>
                            </div>
                        )}

                        {!loading && selectedReport && (
                            <motion.div
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ duration: 0.5 }}
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
                                                <Clock className="w-3 h-3" /> {new Date().toLocaleDateString()}
                                            </span>
                                        </div>
                                        <h1 className="text-4xl md:text-5xl font-display font-bold text-white leading-tight">
                                            {selectedReport.title || "Health Analysis"}
                                        </h1>
                                        <div className="flex items-center gap-2 mt-4 text-zinc-400">
                                            <FileText className="w-4 h-4" />
                                            <span className="font-mono text-sm">{selectedReport.filename}</span>
                                        </div>
                                    </div>

                                    <div className={`
                                        flex items-center gap-3 px-6 py-4 rounded-2xl border backdrop-blur-sm
                                        ${selectedReport.risk_score > 6 ? 'bg-error/10 border-error/20 text-error' :
                                            selectedReport.risk_score > 3 ? 'bg-warning/10 border-warning/20 text-warning' :
                                                'bg-success/10 border-success/20 text-success'}
                                    `}>
                                        <div className="text-right">
                                            <div className="text-xs font-bold uppercase tracking-wider opacity-80">Risk Score</div>
                                            <div className="text-3xl font-display font-bold">{selectedReport.risk_score}/10</div>
                                        </div>
                                        <Activity className="w-8 h-8 opacity-80" />
                                    </div>
                                </div>

                                {/* Key Metrics Grid */}
                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                                    {selectedReport.param_interpretation && Object.entries(selectedReport.param_interpretation).map(([key, data]) => {
                                        const isAbnormal = data.status !== 'normal';
                                        return (
                                            <motion.div
                                                key={key}
                                                whileHover={{ y: -5 }}
                                                className={`
                                                    p-5 rounded-xl border transition-all duration-300
                                                    ${isAbnormal ? 'bg-white/10 border-white/20' : 'bg-white/5 border-white/5'}
                                                `}
                                            >
                                                <div className="flex justify-between items-start mb-3">
                                                    <div className="text-sm font-medium text-zinc-400">{key}</div>
                                                    <div className={`
                                                        w-2 h-2 rounded-full
                                                        ${data.status === 'high' ? 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.8)]' :
                                                            data.status === 'low' ? 'bg-yellow-500 shadow-[0_0_8px_rgba(234,179,8,0.8)]' :
                                                                'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.8)]'}
                                                    `} />
                                                </div>
                                                <div className="text-2xl font-bold text-white mb-1">
                                                    {data.value} <span className="text-sm font-normal text-zinc-500">{data.unit}</span>
                                                </div>
                                                <div className="text-xs text-zinc-600 font-mono">
                                                    Ref: {data.reference?.low} - {data.reference?.high}
                                                </div>
                                            </motion.div>
                                        )
                                    })}
                                </div>

                                {/* Deep Analysis Section */}
                                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                                    {/* Clinical Synthesis */}
                                    <div className="lg:col-span-2 glass-card rounded-3xl p-8 border-white/10 relative overflow-hidden">
                                        <div className="absolute top-0 right-0 w-64 h-64 bg-primary/10 rounded-full blur-[80px] -mr-20 -mt-20 pointer-events-none" />

                                        <h3 className="text-xl font-bold text-white mb-6 flex items-center gap-3 relative z-10">
                                            <div className="p-2 bg-primary/20 rounded-lg text-primary"><FileText className="w-5 h-5" /></div>
                                            Clinical Synthesis
                                        </h3>

                                        <div className="prose prose-invert prose-p:text-zinc-300 prose-strong:text-white max-w-none relative z-10">
                                            {Array.isArray(selectedReport.synthesis_report) ? (
                                                selectedReport.synthesis_report.map((block, idx) => (
                                                    <div key={idx} dangerouslySetInnerHTML={{
                                                        __html: block
                                                            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                                                            .replace(/\n/g, '<br />')
                                                    }} className="mb-4" />
                                                ))
                                            ) : (
                                                <div dangerouslySetInnerHTML={{
                                                    __html: (selectedReport.synthesis_report || "")
                                                        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                                                        .replace(/\n/g, '<br />')
                                                }} />
                                            )}
                                        </div>
                                    </div>

                                    {/* Side Info: Patterns & Risk */}
                                    <div className="space-y-6">
                                        <div className="glass-card rounded-3xl p-6 border-white/10">
                                            <h3 className="font-bold text-white mb-4 flex items-center gap-2">
                                                <ShieldAlert className="w-5 h-5 text-accent" />
                                                Risk Assessment
                                            </h3>
                                            <div className="text-sm text-zinc-300 leading-relaxed">
                                                {Array.isArray(selectedReport.risk_rationale) ? (
                                                    <ul className="space-y-2">
                                                        {selectedReport.risk_rationale.map((reason, idx) => (
                                                            <li key={idx} className="flex gap-2">
                                                                <span className="text-accent mt-1">•</span>
                                                                {reason}
                                                            </li>
                                                        ))}
                                                    </ul>
                                                ) : (
                                                    <p>{selectedReport.risk_rationale || "No specific risk rationale provided."}</p>
                                                )}
                                            </div>
                                        </div>

                                        <div className="glass-card rounded-3xl p-6 border-white/10">
                                            <h3 className="font-bold text-white mb-4 flex items-center gap-2">
                                                <Activity className="w-5 h-5 text-primary" />
                                                Patterns Detected
                                            </h3>
                                            <div className="flex flex-wrap gap-2">
                                                {selectedReport.patterns && selectedReport.patterns.length > 0 ? (
                                                    selectedReport.patterns.map((pat, i) => (
                                                        <span key={i} className="px-3 py-1 rounded-lg bg-surfaceHighlight border border-white/5 text-xs text-zinc-300">
                                                            {pat}
                                                        </span>
                                                    ))
                                                ) : <span className="text-zinc-500 text-sm italic">No specific patterns.</span>}
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                {/* Recommendations */}
                                {selectedReport.recommendations && selectedReport.recommendations.length > 0 && (
                                    <div className="glass-card rounded-3xl p-8 border-white/10 bg-gradient-to-br from-surface/60 to-surface/40">
                                        <h3 className="text-xl font-bold text-white mb-6 flex items-center gap-3">
                                            <div className="p-2 bg-green-500/20 rounded-lg text-green-500"><CheckCircle className="w-5 h-5" /></div>
                                            Recommendations
                                        </h3>
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                            {selectedReport.recommendations.map((rec, i) => (
                                                <div key={i} className="flex gap-3 p-4 rounded-xl bg-white/5 border border-white/5 hover:bg-white/10 transition-colors">
                                                    <Check className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
                                                    <span className="text-zinc-300 text-sm leading-relaxed">{rec}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* AI Chat Interface Integration */}
                                {selectedReport.rag_collection_name && (
                                    <div className="pt-8">
                                        <div className=" glass-card rounded-3xl overflow-hidden border-white/10">
                                            <div className="p-6 border-b border-white/10 bg-white/5">
                                                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                                                    <Sparkles className="w-5 h-5 text-primary" />
                                                    Ask AI about this report
                                                </h3>
                                            </div>
                                            <div className="p-0">
                                                <ChatComponent collectionName={selectedReport.rag_collection_name} sessionId={sessionId} />
                                            </div>
                                        </div>
                                    </div>
                                )}

                            </motion.div>
                        )}
                    </div>
                </div>

                {/* Settings Drawer (Overlay) */}
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
                                    <button onClick={() => setShowSettings(false)} className="p-2 hover:bg-white/10 rounded-full transition-colors"><X size={20} /></button>
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
                                                <p className="text-zinc-500 text-sm">{user.email}</p>
                                                <button onClick={() => setIsEditing(true)} className="mt-4 text-primary text-sm hover:underline">Edit Profile</button>
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
                                                    <button type="button" onClick={() => setIsEditing(false)} className="flex-1 py-2 rounded-lg bg-zinc-800 text-sm font-medium">Cancel</button>
                                                    <button type="submit" disabled={updatingProfile} className="flex-1 py-2 rounded-lg bg-primary text-white text-sm font-medium">
                                                        {updatingProfile ? "Saving..." : "Save"}
                                                    </button>
                                                </div>
                                            </form>
                                        )}
                                    </div>

                                    <div className="border-t border-white/10 pt-6">
                                        <button onClick={handleLogout} className="w-full py-3 rounded-xl bg-error/10 text-error font-medium hover:bg-error/20 transition-colors flex items-center justify-center gap-2">
                                            <LogOut size={18} /> Sign Out
                                        </button>
                                    </div>
                                </div>
                            </motion.div>
                        </>
                    )}
                </AnimatePresence>

            </div>
        </div>
    );
}
