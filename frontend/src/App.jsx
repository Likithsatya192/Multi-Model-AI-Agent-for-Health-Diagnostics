import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import Login from './pages/Login';
import Signup from './pages/Signup';
import Dashboard from './pages/Dashboard';
import { onAuthStateChanged } from 'firebase/auth';
import { auth } from './firebase';

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [authError, setAuthError] = useState(null);

  useEffect(() => {
    // Check if auth is initialized (it might be null if config is missing)
    if (!auth) {
      setAuthError("Firebase API Key is missing. Check local .env file.");
      setLoading(false);
      return;
    }

    try {
      const unsubscribe = onAuthStateChanged(auth,
        (currentUser) => {
          setUser(currentUser);
          setLoading(false);
        },
        (error) => {
          console.error("Auth Error:", error);
          setAuthError(error.message);
          setLoading(false);
        }
      );
      return () => unsubscribe();
    } catch (err) {
      console.error("Auth Setup Error:", err);
      setAuthError(err.message);
      setLoading(false);
    }
  }, []);

  if (authError) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-zinc-950 text-red-500 p-4 text-center font-sans">
        <h1 className="text-3xl font-bold mb-4">Configuration Error</h1>
        <div className="bg-zinc-900 p-6 rounded-lg border border-red-900/50 max-w-md">
          <p className="text-zinc-300 mb-4">{authError}</p>
          <div className="text-sm text-zinc-500 bg-black p-3 rounded text-left font-mono">
            VITE_FIREBASE_API_KEY=...
          </div>
          <p className="text-zinc-500 mt-4 text-sm">Please check your <code>frontend/.env</code> file.</p>
        </div>
      </div>
    );
  }

  if (loading) return (
    <div className="h-screen flex items-center justify-center bg-zinc-950 text-white">
      <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
    </div>
  );

  return (
    <Router>
      <Routes>
        <Route path="/login" element={!user ? <Login /> : <Navigate to="/" />} />
        <Route path="/signup" element={!user ? <Signup /> : <Navigate to="/" />} />
        <Route path="/" element={user ? <Dashboard user={user} /> : <Navigate to="/login" />} />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </Router>
  );
}

export default App;
