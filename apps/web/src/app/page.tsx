"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { env } from "@/config/env";
import { AIWorkspace } from "@/components/ui/ai-workspace";
import { Spotlight } from "@/components/ui/spotlight";

export default function LandingPage() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [currency, setCurrency] = useState("inr");
  const [loading, setLoading] = useState(false);
  const [detectedIntent, setDetectedIntent] = useState<any>(null);
  const [isDetecting, setIsDetecting] = useState(false);

  useEffect(() => {
    // Inject dark class to html to force premium dark mode styling
    document.documentElement.classList.add("dark");
  }, []);

  // Debounced Intent Detection
  useEffect(() => {
    const timer = setTimeout(async () => {
      if (title.trim().length >= 3) {
        setIsDetecting(true);
        try {
          const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/api/decisions/detect-intent`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query: title.trim() }),
          });
          if (res.ok) {
            const data = await res.json();
            setDetectedIntent(data);
          }
        } catch (e) {
          // Silent ignore
        } finally {
          setIsDetecting(false);
        }
      } else {
        setDetectedIntent(null);
      }
    }, 400); // 400ms debounce
    return () => clearTimeout(timer);
  }, [title]);

  const handleStart = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      toast.error("Please enter a title for your decision session.");
      return;
    }

    setLoading(true);

    try {
      // 1. Generate or fetch anonymous guest ID
      let guestId = localStorage.getItem("nexus_guest_id");
      if (!guestId) {
        guestId = crypto.randomUUID();
        localStorage.setItem("nexus_guest_id", guestId);
      }

      // 2. Set session cookie for Next.js middleware protection bypass
      document.cookie = `session_token=${guestId}; path=/; max-age=31536000`;
      localStorage.setItem("nexus_user", JSON.stringify({ id: guestId, email: `guest-${guestId}@nexus.ai`, name: "Guest User" }));

      // 3. POST request to backend API to initialize decision session
      const response = await fetch(`${env.NEXT_PUBLIC_API_URL}/api/decisions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Guest-ID": guestId,
        },
        body: JSON.stringify({
          title: title.trim(),
          category: null, // dynamic auto-detection from title on backend!
          currency: currency,
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to initialize decision session on the backend.");
      }

      const decision = await response.json();
      toast.success(`Started decision session! Auto-detected category: ${decision.category}`);
      
      // Navigate to questionnaire wizard
      router.push(`/decide/${decision.id}`);
    } catch (err: any) {
      toast.error(err.message || "An unexpected error occurred. Is the backend server running?");
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col justify-between selection:bg-indigo-500 selection:text-white relative overflow-hidden">
      {/* Spotlight Ambient Glow */}
      <Spotlight
        className="-top-40 left-0 md:left-60 md:-top-20"
        fill="white"
      />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(99,102,241,0.08),transparent_40%),radial-gradient(circle_at_bottom_left,rgba(168,85,247,0.06),transparent_35%)] pointer-events-none" />

      {/* Header */}
      <header className="max-w-7xl mx-auto w-full px-6 py-6 flex items-center justify-between z-20">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-indigo-500 to-purple-600 flex items-center justify-center font-bold text-lg text-white shadow-lg shadow-indigo-500/20">
            N
          </div>
          <span className="font-accent text-xl font-bold tracking-tight bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
            Nexus
          </span>
        </div>
        <div className="text-sm text-slate-400 border border-slate-800/80 rounded-full px-3 py-1 bg-slate-900/50 backdrop-blur-sm">
          Guest Sandbox Mode
        </div>
      </header>

      {/* Hero Body - Two Column Layout */}
      <main className="max-w-7xl mx-auto w-full px-4 sm:px-6 py-8 sm:py-12 flex-grow flex flex-col md:flex-row items-center justify-between gap-12 z-10">
        {/* Left Column: Text & Form */}
        <div className="flex-grow flex-shrink-0 w-full md:w-1/2 flex flex-col items-start text-left max-w-xl">
          {/* Animated Feature Tag */}
          <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-indigo-500/30 bg-indigo-500/10 text-indigo-300 text-xs font-semibold tracking-wide uppercase mb-6 animate-pulse">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
            AI Category Detection Enabled
          </div>

          <h1 className="font-accent text-4xl md:text-6xl font-bold tracking-tight text-white mb-6 leading-[1.15]">
            Every decision.{" "}
            <span className="bg-gradient-to-r from-indigo-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
              Smarter.
            </span>
          </h1>
          <p className="text-slate-400 text-lg mb-10 leading-relaxed">
            Describe what you are buying. Nexus automatically detects the category, determines your persona, maps your preferences dynamically, and scores the catalog.
          </p>

          {/* Input box card */}
          <div className="w-full p-1 rounded-2xl bg-gradient-to-tr from-slate-800 via-slate-900 to-slate-800 shadow-2xl shadow-indigo-500/5 border border-slate-800/80 backdrop-blur-xl">
            <form onSubmit={handleStart} className="flex flex-col gap-4 p-5 bg-slate-950/80 rounded-[14px]">
              <div>
                <label htmlFor="title" className="block text-left text-xs font-semibold uppercase text-slate-400 tracking-wider mb-2">
                  What are you looking for?
                </label>
                <div className="relative">
                  <input
                    id="title"
                    type="text"
                    value={title}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setTitle(e.target.value)}
                    placeholder="e.g. Gaming laptop, smartphone for photography, 4K monitor..."
                    className="w-full px-4 py-3 rounded-lg border border-slate-800 bg-slate-900/60 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all font-medium"
                    disabled={loading}
                  />
                  {/* Instant Feedback Overlay */}
                  {detectedIntent && (
                    <div className="absolute top-full left-0 right-0 mt-2 bg-slate-900 border border-indigo-500/30 rounded-lg p-3 shadow-xl z-20 animate-in fade-in slide-in-from-top-2 flex flex-wrap items-center justify-between gap-2 text-xs">
                      <div className="flex items-center gap-1.5 text-slate-300">
                        <span className="text-indigo-400 font-semibold">Category:</span> <span className="capitalize">{detectedIntent.category}</span>
                      </div>
                      <div className="flex items-center gap-1.5 text-slate-300">
                        <span className="text-indigo-400 font-semibold">Subtype:</span> <span className="capitalize">{detectedIntent.subcategory}</span>
                      </div>
                      <div className="flex items-center gap-1.5 text-slate-300">
                        <span className="text-indigo-400 font-semibold">Persona:</span> <span className="capitalize">{detectedIntent.persona || "General"}</span>
                      </div>
                      <div className="flex items-center gap-1.5 text-slate-300">
                        <span className="text-emerald-400 font-semibold">Confidence:</span> {Math.round(detectedIntent.confidence)}%
                      </div>
                      <div className="flex items-center gap-1.5 text-slate-300">
                        <span className="text-indigo-400 font-semibold">Questions:</span> {detectedIntent.questions_count}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              <div className="flex flex-col sm:flex-row gap-4">
                <div className="flex-grow">
                  <label className="block text-left text-xs font-semibold uppercase text-slate-400 tracking-wider mb-2">
                    Currency Preference
                  </label>
                  <select
                    value={currency}
                    onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setCurrency(e.target.value)}
                    className="w-full px-4 py-3 rounded-lg border border-slate-800 bg-slate-900/60 text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all font-medium cursor-pointer"
                    disabled={loading}
                  >
                    <option value="inr">INR (₹) Indian Rupees</option>
                    <option value="usd">USD ($) US Dollars</option>
                  </select>
                </div>

                <div className="flex flex-col justify-end w-full sm:w-auto">
                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full h-[46px] px-6 rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 text-white font-bold transition-all shadow-lg shadow-indigo-500/25 flex items-center justify-center gap-2 hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 disabled:scale-100 disabled:pointer-events-none"
                  >
                    {loading ? (
                      <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    ) : (
                      "Start Decision"
                    )}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>

        {/* Right Column: AI Workspace */}
        <div className="flex-grow w-full md:w-1/2 h-[350px] md:h-[550px] relative">
          <AIWorkspace inputValue={title} isAnalyzing={loading || isDetecting} detectedIntent={detectedIntent} />
        </div>
      </main>

      {/* Footer */}
      <footer className="py-6 border-t border-slate-900 text-center text-xs text-slate-500 z-10 bg-slate-950/20 backdrop-blur-sm">
        &copy; 2026 Nexus AI Decision Engine. Built with FastAPI, Next.js, and Google Gemini.
      </footer>
    </div>
  );
}
