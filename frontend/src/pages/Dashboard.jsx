import { useState, useEffect } from 'react';
import { signOut, updateProfile } from 'firebase/auth';
import { auth } from '../firebase';
import axios from 'axios';
import { LogOut, Upload, AlertCircle, CheckCircle, Clock, ArrowLeft, FileText, Settings, User, Camera, X, Loader2, Edit2, ChevronRight, Save, PlusCircle, FileSearch, Check, ShieldAlert, Activity } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export default function Dashboard({ user }) {
    // State
    const [selectedReport, setSelectedReport] = useState(null);
    const [loading, setLoading] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [file, setFile] = useState(null);

    // Settings State
    const [showSettings, setShowSettings] = useState(false);
    const [isEditing, setIsEditing] = useState(false);
    const [userName, setUserName] = useState(user.displayName || '');
    // Initialize photo from localStorage or Auth
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

        // Reset report only when starting the actual analysis
        setSelectedReport(null);
        setUploading(true);
        setLoading(true);

        const formData = new FormData();
        formData.append("file", file);

        try {
            // Call Python API directly
            const response = await axios.post("http://localhost:8000/analyze", formData, {
                headers: { "Content-Type": "multipart/form-data" },
                timeout: 300000 // 5 minute timeout
            });

            const analysisResult = response.data;

            if (analysisResult.errors && analysisResult.errors.length > 0) {
                alert("Analysis Issues Found:\n" + analysisResult.errors.join("\n"));
                // We still show the report if there is partial data, or we could stop.
                // For now, let's allow partial data but warn the user.
            }

            // Generate a fancy title based on content if possible, else default
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
            setFile(null); // Clear file after analysis to reset the button state
        }
    };

    const handleLogout = () => signOut(auth);

    // Handle Photo Upload (Convert to Base64)
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
                // Note: We don't update photoURL here to avoid Firebase limits. LocalStorage handles it.
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
        <div className="min-h-screen bg-background text-zinc-100 font-sans selection:bg-primary/30">

            {/* Scrolling Container for EVERYTHING */}
            <div className="w-full h-full flex flex-col relative">

                {/* Header (Scrolls with page) */}
                <div className="w-full p-6 flex items-center justify-between z-20">
                    <div className="flex-1 md:flex-none">
                        {/* Placeholder for Logo if needed, otherwise empty space or Title if showing on Dashboard */}
                    </div>

                    <div className="flex items-center gap-4">
                        {/* User Display (Name/Avatar/Email) */}
                        <div className="flex items-center gap-3 mr-2 hidden md:flex animate-in fade-in slide-in-from-right-4 duration-700">
                            {/* Tiny Avatar in Header */}
                            <div className="w-9 h-9 rounded-full bg-zinc-800 border-2 border-zinc-700 overflow-hidden flex items-center justify-center shadow-lg">
                                {userPhoto ? (
                                    <img src={userPhoto} alt="User" className="w-full h-full object-cover" />
                                ) : (
                                    <User size={16} className="text-zinc-400" />
                                )}
                            </div>
                            <div className="flex flex-col items-end">
                                <span className="font-bold text-sm text-zinc-100 tracking-wide">{user.displayName || "User"}</span>
                                <span className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium">Online</span>
                            </div>
                        </div>

                        <div className="h-8 w-px bg-zinc-800 mx-2 hidden md:block"></div>

                        <button
                            onClick={() => setShowSettings(true)}
                            className="w-10 h-10 rounded-full bg-zinc-900/80 backdrop-blur-md flex items-center justify-center hover:bg-zinc-800 border border-zinc-700 hover:border-zinc-500 transition duration-300 group shadow-lg"
                            title="Settings"
                        >
                            <Settings size={20} className="text-zinc-400 group-hover:text-white transition-transform group-hover:rotate-90" />
                        </button>
                    </div>
                </div>

                {/* Settings Sidebar (Drawer) */}
                <AnimatePresence>
                    {showSettings && (
                        <>
                            {/* Backdrop */}
                            <motion.div
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                exit={{ opacity: 0 }}
                                className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
                                onClick={() => setShowSettings(false)}
                            />

                            {/* Sidebar */}
                            <motion.div
                                initial={{ x: "100%" }}
                                animate={{ x: 0 }}
                                exit={{ x: "100%" }}
                                transition={{ type: "spring", stiffness: 300, damping: 30 }}
                                className="fixed top-0 right-0 z-50 h-full w-full max-w-sm bg-zinc-950 border-l border-zinc-800 shadow-2xl flex flex-col"
                            >
                                {/* Header */}
                                <div className="flex items-center justify-between p-6 border-b border-zinc-900">
                                    <h2 className="text-xl font-bold text-white flex items-center gap-2">
                                        <Settings size={20} className="text-primary" /> Settings
                                    </h2>
                                    <button onClick={() => setShowSettings(false)} className="p-2 hover:bg-zinc-900 rounded-full text-zinc-500 hover:text-white transition">
                                        <X size={20} />
                                    </button>
                                </div>

                                {/* Content */}
                                <div className="flex-1 overflow-y-auto p-6">
                                    <div className="flex flex-col items-center mb-8 relative">
                                        <div className="w-32 h-32 rounded-full bg-zinc-900 border-4 border-zinc-800 flex items-center justify-center overflow-hidden mb-4 shadow-xl relative group">
                                            {userPhoto ? (
                                                <img src={userPhoto} alt="Profile" className="w-full h-full object-cover" />
                                            ) : (
                                                <span className="text-4xl font-bold text-zinc-600">
                                                    {(userName || user.email || "?")[0].toUpperCase()}
                                                </span>
                                            )}

                                            {/* Edit Overlay for Photo */}
                                            {isEditing && (
                                                <label className="absolute inset-0 bg-black/60 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer">
                                                    <Camera size={24} className="text-white" />
                                                    <input type="file" accept="image/*" onChange={handlePhotoUpload} className="hidden" />
                                                </label>
                                            )}
                                        </div>
                                        {!isEditing && (
                                            <>
                                                <h3 className="text-2xl font-bold text-white mb-1">{userName || "No Name Set"}</h3>
                                                <p className="text-sm text-zinc-500">{user.email}</p>
                                            </>
                                        )}
                                    </div>

                                    <AnimatePresence mode="wait">
                                        {isEditing ? (
                                            <motion.div
                                                key="edit"
                                                initial={{ opacity: 0, y: 10 }}
                                                animate={{ opacity: 1, y: 0 }}
                                                exit={{ opacity: 0, y: -10 }}
                                                className="space-y-4"
                                            >
                                                <form onSubmit={handleUpdateProfile} className="space-y-4">
                                                    <div>
                                                        <label className="block text-xs uppercase text-zinc-500 font-bold mb-2">Display Name</label>
                                                        <div className="relative">
                                                            <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
                                                            <input
                                                                type="text"
                                                                value={userName}
                                                                onChange={(e) => setUserName(e.target.value)}
                                                                className="w-full bg-zinc-900 border border-zinc-800 rounded-lg py-3 pl-10 pr-4 text-zinc-200 focus:outline-none focus:border-primary transition"
                                                                placeholder="Your Name"
                                                            />
                                                        </div>
                                                    </div>

                                                    <div className="flex gap-2 pt-4">
                                                        <button
                                                            type="button"
                                                            onClick={() => { setIsEditing(false); setUserName(user.displayName || ''); }}
                                                            className="flex-1 bg-zinc-800 hover:bg-zinc-700 text-white font-medium py-3 rounded-xl transition"
                                                        >
                                                            Cancel
                                                        </button>
                                                        <button
                                                            type="submit"
                                                            disabled={updatingProfile}
                                                            className="flex-1 bg-primary hover:bg-blue-600 text-white font-medium py-3 rounded-xl transition flex items-center justify-center gap-2"
                                                        >
                                                            {updatingProfile ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Save size={18} /> Save Changes</>}
                                                        </button>
                                                    </div>
                                                </form>
                                            </motion.div>
                                        ) : (
                                            <motion.div
                                                key="view"
                                                initial={{ opacity: 0, y: 10 }}
                                                animate={{ opacity: 1, y: 0 }}
                                                exit={{ opacity: 0, y: -10 }}
                                                className="space-y-3"
                                            >
                                                <button
                                                    onClick={() => setIsEditing(true)}
                                                    className="w-full bg-zinc-900 hover:bg-zinc-800 text-white border border-zinc-800 hover:border-zinc-700 font-medium py-4 rounded-xl transition flex items-center justify-between px-6 group"
                                                >
                                                    <span className="flex items-center gap-3 text-lg"><Edit2 size={20} className="text-primary" /> Edit Profile</span>
                                                    <ChevronRight size={20} className="text-zinc-600 group-hover:text-zinc-400" />
                                                </button>
                                            </motion.div>
                                        )}
                                    </AnimatePresence>
                                </div>

                                {/* Footer */}
                                <div className="p-6 border-t border-zinc-900">
                                    <button
                                        onClick={handleLogout}
                                        className="w-full bg-red-500/10 hover:bg-red-500/20 text-red-500 border border-red-500/20 hover:border-red-500/30 font-medium py-4 rounded-xl transition flex items-center justify-center gap-2"
                                    >
                                        <LogOut size={20} /> Log Out
                                    </button>
                                </div>
                            </motion.div>
                        </>
                    )}
                </AnimatePresence>

                {/* Main Content Area */}
                <div className="flex-1 w-full max-w-7xl mx-auto p-6 md:p-12 mb-20 animate-in fade-in duration-500">

                    {loading ? (
                        <div className="flex flex-col items-center justify-center min-h-[50vh] text-secondary">
                            <div className="animate-spin rounded-full h-20 w-20 border-t-4 border-b-4 border-primary mb-8 shadow-[0_0_30px_rgba(59,130,246,0.2)]"></div>
                            <p className="text-2xl animate-pulse font-light tracking-wide text-zinc-300">{uploading ? "Analyzing Report..." : "Loading..."}</p>
                            <p className="text-sm text-zinc-500 mt-2">Our AI is synthesizing clinical data</p>
                        </div>
                    ) : !selectedReport ? (
                        // Upload View
                        <div className="flex flex-col items-center justify-center min-h-[60vh] text-center w-full">

                            {/* Header */}
                            <div className="mb-12 space-y-4">
                                <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight bg-gradient-to-br from-white via-zinc-200 to-zinc-500 bg-clip-text text-transparent drop-shadow-xl">
                                    Health AI Analyzer
                                </h1>
                                <p className="text-xl md:text-2xl font-light text-zinc-400 max-w-2xl mx-auto leading-relaxed">
                                    Upload your medical report. Get instant, AI-powered health insights.
                                </p>
                            </div>

                            {/* Upload Area */}
                            <div className="relative group w-full max-w-xl mx-auto">
                                <div className="absolute inset-0 bg-gradient-to-r from-blue-600 to-purple-600 rounded-3xl blur-2xl opacity-15 group-hover:opacity-30 transition duration-700"></div>

                                <label className="relative block cursor-pointer">
                                    <input
                                        type="file"
                                        accept=".pdf,image/*"
                                        className="hidden"
                                        onChange={(e) => setFile(e.target.files[0])}
                                    />
                                    <div className={`
                                        bg-zinc-900/80 backdrop-blur-xl border-2 border-dashed
                                        ${file ? 'border-green-500/50 bg-green-500/5' : 'border-zinc-700 hover:border-zinc-500 hover:bg-zinc-800/80'}
                                        rounded-3xl p-16 transition-all duration-300
                                        flex flex-col items-center justify-center gap-6 shadow-2xl
                                    `}>
                                        <div className={`p-4 rounded-full ${file ? 'bg-green-500/20 text-green-400' : 'bg-primary/10 text-primary'} transition-colors duration-300`}>
                                            {file ? <CheckCircle size={48} /> : <Upload size={48} />}
                                        </div>

                                        <div className="space-y-2">
                                            <div className="text-2xl font-bold text-white">
                                                {file ? file.name : "Select Document"}
                                            </div>
                                            <div className="text-sm text-zinc-500 uppercase tracking-widest font-bold">
                                                {file ? "Ready to Analyze" : "PDF or Image"}
                                            </div>
                                        </div>
                                    </div>
                                </label>
                            </div>

                            <AnimatePresence>
                                {file && (
                                    <motion.button
                                        initial={{ opacity: 0, y: 10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        exit={{ opacity: 0, y: 10 }}
                                        onClick={handleAnalysis}
                                        className="mt-12 bg-white text-zinc-950 hover:bg-zinc-200 px-12 py-5 rounded-full font-bold text-lg shadow-[0_0_20px_rgba(255,255,255,0.3)] transition hover:scale-105 active:scale-95 flex items-center gap-3"
                                    >
                                        Run Analysis <Clock size={20} />
                                    </motion.button>
                                )}
                            </AnimatePresence>
                        </div>
                    ) : (
                        // Report View
                        <div className="w-full animate-in slide-in-from-bottom-8 duration-700">

                            {/* Report Header & Actions */}
                            <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 mb-12 border-b border-zinc-800 pb-8">
                                <div>
                                    <h1 className="text-4xl md:text-5xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-blue-100 via-white to-blue-200 mb-3 drop-shadow-sm">
                                        {selectedReport.title || "Comprehensive Health Analysis"}
                                    </h1>
                                    <div className="flex items-center gap-4 text-sm text-zinc-400">
                                        <span className="flex items-center gap-1.5"><FileSearch size={16} className="text-primary" /> {selectedReport.filename}</span>
                                        <div className="w-1.5 h-1.5 rounded-full bg-zinc-700"></div>
                                        <div className={`flex items-center gap-2 px-3 py-1 rounded-full text-xs font-bold bg-zinc-900 border ${selectedReport.risk_score > 6 ? 'border-red-500/50 text-red-500 shadow-[0_0_10px_rgba(239,68,68,0.2)]' : selectedReport.risk_score > 3 ? 'border-yellow-500/50 text-yellow-500 shadow-[0_0_10px_rgba(234,179,8,0.2)]' : 'border-green-500/50 text-green-500 shadow-[0_0_10px_rgba(34,197,94,0.2)]'}`}>
                                            <Activity size={14} /> Risk Level: {selectedReport.risk_score}/10
                                        </div>
                                    </div>
                                </div>

                                {/* Refactored Action Button */}
                                <div>
                                    {file ? (
                                        // If a new file is pending (selected but not run yet)
                                        <button
                                            onClick={handleAnalysis}
                                            className="flex items-center gap-2 bg-green-500 hover:bg-green-600 text-white px-8 py-4 rounded-full font-bold transition shadow-[0_0_20px_rgba(34,197,94,0.4)] active:scale-95 whitespace-nowrap animate-pulse"
                                        >
                                            <Clock size={20} /> Analyze {file.name}
                                        </button>
                                    ) : (
                                        // Default: Button acts as a file picker label
                                        <label className="flex items-center gap-2 bg-zinc-900 hover:bg-zinc-800 text-white px-8 py-4 rounded-full font-bold transition shadow-lg hover:shadow-primary/10 border border-zinc-800 hover:border-primary/30 active:scale-95 whitespace-nowrap cursor-pointer hover:text-primary">
                                            <input
                                                type="file"
                                                className="hidden"
                                                accept=".pdf,image/*"
                                                onChange={(e) => setFile(e.target.files[0])}
                                            />
                                            <PlusCircle size={20} /> Analyze Another Report
                                        </label>
                                    )}
                                </div>
                            </div>

                            {/* Key Parameters Grid */}
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5 mb-12">
                                {selectedReport.param_interpretation && Object.entries(selectedReport.param_interpretation).map(([key, data]) => {
                                    const statusColor = data.status === 'high' ? 'text-red-400' : data.status === 'low' ? 'text-yellow-400' : 'text-green-400';
                                    const cardBg = data.status !== 'normal' ? 'bg-zinc-900/60 border-zinc-700/60' : 'bg-black/40 border-zinc-800';

                                    return (
                                        <div key={key} className={`${cardBg} border p-6 rounded-2xl hover:border-zinc-500/50 transition duration-300 group`}>
                                            <div className="flex justify-between items-start mb-3">
                                                <h3 className="text-sm font-bold text-zinc-400 truncate pr-2 group-hover:text-zinc-200 transition">{key}</h3>
                                                <span className={`text-[10px] uppercase font-extrabold px-2 py-1 rounded bg-white/5 tracking-wider ${statusColor}`}>{data.status}</span>
                                            </div>
                                            <div className="text-3xl font-extrabold text-white mb-2">
                                                {data.value} <span className="text-xs font-medium text-zinc-500 ml-1">{data.unit}</span>
                                            </div>
                                            <div className="text-xs text-zinc-600 font-mono group-hover:text-zinc-500 transition">Range: {data.reference?.low} - {data.reference?.high}</div>
                                        </div>
                                    )
                                })}
                            </div>

                            {/* NEW LAYOUT: Stacked Rows */}

                            {/* ROW 1: Risk Assessment & Patterns Detected */}
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-8">

                                {/* Risk Rationale Card */}
                                <div className="bg-gradient-to-b from-zinc-900 via-zinc-900 to-black p-8 rounded-3xl border border-zinc-800 shadow-xl relative overflow-hidden group">
                                    <div className="absolute inset-0 bg-red-500/5 opacity-0 group-hover:opacity-100 transition duration-700 pointer-events-none"></div>
                                    <h3 className="text-xl font-extrabold mb-4 flex items-center gap-3 text-white">
                                        <ShieldAlert size={24} className="text-red-500" /> Risk Assessment
                                    </h3>
                                    <div className="prose prose-invert prose-sm text-zinc-300 leading-relaxed">
                                        {Array.isArray(selectedReport.risk_rationale) ? (
                                            <ul className="list-disc pl-5 space-y-2">
                                                {selectedReport.risk_rationale.map((reason, idx) => (
                                                    <li key={idx}>{reason}</li>
                                                ))}
                                            </ul>
                                        ) : (
                                            <p>{selectedReport.risk_rationale || "No specific risk rationale provided."}</p>
                                        )}
                                    </div>
                                </div>

                                {/* Patterns Patterns Card */}
                                <div className="bg-gradient-to-b from-zinc-900 via-zinc-900 to-black p-8 rounded-3xl border border-zinc-800 shadow-xl">
                                    <h3 className="text-xl font-extrabold mb-6 text-white flex items-center gap-3">
                                        <Activity size={24} className="text-blue-500" /> Patterns Detected
                                    </h3>
                                    <ul className="space-y-4">
                                        {selectedReport.patterns && selectedReport.patterns.length > 0 ? (
                                            selectedReport.patterns.map((pat, i) => (
                                                <li key={i} className="flex items-start gap-4 text-zinc-300 bg-zinc-900/50 p-3 rounded-xl border border-zinc-800/50">
                                                    <span className="mt-1 w-2 h-2 rounded-full bg-blue-500 shrink-0 shadow-[0_0_8px_rgba(59,130,246,0.8)]"></span>
                                                    <span className="font-medium">{pat}</span>
                                                </li>
                                            ))
                                        ) : <li className="text-zinc-500 italic p-2">No specific patterns detected.</li>}
                                    </ul>
                                </div>
                            </div>

                            {/* ROW 2: Clinical Synthesis (Full Width) */}
                            <div className="mb-8 hidden-scrollbar">
                                <div className="bg-gradient-to-br from-zinc-900 to-zinc-950 p-10 rounded-[2rem] border border-zinc-800/80 shadow-2xl relative overflow-hidden min-h-[400px]">
                                    <div className="absolute top-0 right-0 w-96 h-96 bg-primary/10 rounded-full blur-3xl -mr-20 -mt-20 pointer-events-none"></div>

                                    <div className="relative z-10">
                                        <h3 className="text-3xl font-extrabold mb-8 text-white flex items-center gap-4">
                                            <div className="p-3 bg-blue-500/20 rounded-2xl text-blue-400 shadow-[0_0_15px_rgba(59,130,246,0.3)]"><FileText size={32} /></div>
                                            Clinical Synthesis
                                        </h3>
                                        <div className="prose prose-invert prose-lg max-w-none text-zinc-300 leading-relaxed space-y-4 prose-strong:text-white prose-strong:font-bold prose-headings:text-primary">
                                            {Array.isArray(selectedReport.synthesis_report) ? (
                                                selectedReport.synthesis_report.map((block, idx) => (
                                                    <div key={idx} dangerouslySetInnerHTML={{
                                                        __html: block
                                                            .replace(/\*\*(.*?)\*\*/g, '<strong class="text-white">$1</strong>')
                                                            .replace(/\n/g, '<br />')
                                                    }} />
                                                ))
                                            ) : (
                                                <div className="whitespace-pre-line" dangerouslySetInnerHTML={{
                                                    __html: (selectedReport.synthesis_report || "")
                                                        .replace(/\*\*(.*?)\*\*/g, '<strong class="text-white">$1</strong>')
                                                }} />
                                            )}
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* ROW 3: Recommendations (Full Width) */}
                            {selectedReport.recommendations && selectedReport.recommendations.length > 0 && (
                                <div className="mb-20">
                                    <div className="bg-gradient-to-br from-green-950/20 to-zinc-950 p-8 rounded-3xl border border-green-900/30 shadow-xl relative overflow-hidden">
                                        <div className="absolute bottom-0 left-0 w-32 h-32 bg-green-500/10 rounded-full blur-2xl -ml-10 -mb-10 pointer-events-none"></div>

                                        <div className="relative z-10">
                                            <h3 className="text-xl font-extrabold mb-6 text-white flex items-center gap-3">
                                                <CheckCircle size={24} className="text-green-500" /> Recommendations
                                            </h3>
                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                {selectedReport.recommendations.map((rec, i) => (
                                                    <div key={i} className="flex gap-3 p-4 rounded-xl bg-zinc-900/40 border border-zinc-800/50 hover:border-green-500/20 transition duration-300 items-start">
                                                        <div className="shrink-0 mt-1"><Check size={18} className="text-green-500" /></div>
                                                        <p className="text-zinc-300 font-medium leading-relaxed">{rec}</p>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
