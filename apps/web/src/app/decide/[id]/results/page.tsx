"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";
import { env } from "@/config/env";

interface Recommendation {
  id: string;
  verdict_product: {
    id: string;
    sku: string;
    name: string;
    price: number;
    symbol?: string;
    currency?: string;
    specs: Record<string, any>;
  } | null;
  score: number;
  confidence: number;
  pros: string[];
  cons: string[];
  tradeoffs: any[];
  reasoning: string;
  summary: string;
  citations: string[];
  decision_trace: any;
  display_specs?: { key: string; label: string; unit: string }[];
  status?: string;
  suggestions?: {
    constraint: string;
    label: string;
    current: string;
    recommended: string;
  }[];
  closest_matches?: {
    rank: number;
    sku: string;
    name: string;
    price: number;
    distance: number;
    score: number;
    confidence_score: number;
    checks: {
      key: string;
      label: string;
      status: string;
      value: string;
      deviation: string;
    }[];
  }[];
}

const LOADING_PHASES = [
  "Fetching decision answers from database...",
  "Applying hard spec filters to eliminate out-of-bounds candidates...",
  "Running vector normalization algorithms (Benefit vs Cost)...",
  "Calculating multi-attribute utility dot-products...",
  "Formulating specs tradeoffs and resolving tie-breakers...",
  "Invoking Google Gemini to compile justification narrative...",
  "Preparing structured explainability response..."
];

export default function ResultsPage() {
  const { id } = useParams() as { id: string };
  const router = useRouter();

  const [loading, setLoading] = useState(true);
  const [loadingPhaseIndex, setLoadingPhaseIndex] = useState(0);
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null);
  const [showTrace, setShowTrace] = useState(false);
  const [selectedAlt, setSelectedAlt] = useState<any | null>(null);

  useEffect(() => {
    document.documentElement.classList.add("dark");
    fetchRecommendation();
  }, [id]);

  useEffect(() => {
    if (!loading) return;
    
    // Cycle through loading phase texts to keep the UI engaging
    const interval = setInterval(() => {
      setLoadingPhaseIndex((prev) => (prev + 1) % LOADING_PHASES.length);
    }, 1800);

    return () => clearInterval(interval);
  }, [loading]);

  const fetchRecommendation = async () => {
    try {
      const guestId = localStorage.getItem("nexus_guest_id") || "";
      const response = await fetch(`${env.NEXT_PUBLIC_API_URL}/api/decisions/${id}/recommend`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Guest-ID": guestId,
        },
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Scoring engine evaluation failed.");
      }

      const data = await response.json();
      setRecommendation(data);
      setLoading(false);
    } catch (err: any) {
      toast.error(err.message || "Failed to compile recommendation.");
      // Fallback redirect to start or show error state
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center flex-col gap-6 p-6">
        <span className="w-16 h-16 border-4 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin shadow-lg shadow-indigo-500/10" />
        <div className="text-center max-w-md">
          <h3 className="text-lg font-bold text-white mb-2">Finding Your Perfect Match...</h3>
          <p className="text-sm text-indigo-400 font-medium h-12 transition-all duration-300 animate-pulse">
            {LOADING_PHASES[loadingPhaseIndex]}
          </p>
        </div>
      </div>
    );
  }

  if (!recommendation) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center flex-col gap-4">
        <p className="text-red-400 font-bold">Could not find or calculate a suitable recommendation verdict.</p>
        <button onClick={() => router.push(`/decide/${id}`)} className="px-5 py-2.5 bg-slate-900 border border-slate-800 rounded-lg">
          Modify Answers
        </button>
      </div>
    );
  }

  const isNoMatch = recommendation.status === "no_match_found" || !recommendation.verdict_product;
  const p = recommendation.verdict_product;
  const specMap = p?.specs || {};

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col justify-between selection:bg-indigo-500">
      {/* Background ambient light */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(99,102,241,0.06),transparent_40%),radial-gradient(circle_at_bottom_left,rgba(168,85,247,0.04),transparent_35%)] pointer-events-none" />

      {/* Header */}
      <header className="max-w-7xl mx-auto w-full px-6 py-6 flex items-center justify-between border-b border-slate-900 z-20 bg-slate-950/20 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <button 
            onClick={() => router.push(`/decide/${id}`)}
            className="px-3 py-1.5 rounded-lg border border-slate-855 hover:bg-slate-900 text-slate-400 hover:text-white transition-all text-xs font-semibold"
          >
            &larr; Back to Questions
          </button>
          <span className="text-slate-500 font-bold">/</span>
          <span className="text-xs text-slate-400 font-bold uppercase tracking-wider bg-slate-900 border border-slate-800 px-2 py-0.5 rounded">
            Verdict Page
          </span>
        </div>

        <button 
          onClick={() => router.push("/")}
          className="px-4 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-sm font-semibold transition-all border border-slate-800"
        >
          New Decision
        </button>
      </header>

      {/* Main Results Dashboard */}
      <main className="max-w-6xl mx-auto w-full px-6 py-12 z-10 flex-grow grid grid-cols-1 lg:grid-cols-3 gap-8">
        {isNoMatch ? (
          <>
            {/* Left Column: No Match status card */}
            <div className="lg:col-span-1 flex flex-col gap-6">
              <div className="p-6 rounded-2xl border border-amber-500/20 bg-amber-500/5 backdrop-blur-xl flex flex-col gap-6 relative overflow-hidden">
                <div className="absolute top-0 right-0 w-24 h-24 bg-amber-500/10 rounded-full blur-2xl pointer-events-none" />
                
                <div>
                  <span className="text-xs font-extrabold uppercase tracking-widest text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2.5 py-1 rounded">
                    No Exact Match Found
                  </span>
                  
                  <h1 className="text-xl font-bold text-white mt-6 mb-3 leading-snug">
                    Strict Criteria Constraints
                  </h1>
                  
                  <p className="text-sm text-slate-400 leading-relaxed">
                    No products in our catalog currently satisfy all of your requirements at the same time.
                  </p>
                  
                  <p className="text-xs text-slate-500 mt-4 leading-relaxed">
                    We suggest relaxing one or more filters (such as increasing budget or lowering RAM/storage preferences) to discover suitable products.
                  </p>
                </div>

                <div className="border-t border-slate-800/80 pt-6 flex flex-col gap-3">
                  <button
                    onClick={() => router.push(`/decide/${id}`)}
                    className="w-full py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold transition-all shadow-lg shadow-indigo-600/20 flex items-center justify-center gap-2"
                  >
                    Adjust Requirements &larr;
                  </button>
                </div>
              </div>
            </div>

            {/* Right Column: Suggestions & Closest matches */}
            <div className="lg:col-span-2 flex flex-col gap-6">
              {/* Rationale explanation */}
              <div className="p-6 rounded-2xl border border-slate-800 bg-slate-900/40 backdrop-blur-xl">
                <h2 className="text-lg font-bold text-white mb-4">Shopping Assistant Rationale</h2>
                <p className="text-slate-350 text-sm leading-relaxed mb-4">
                  {recommendation.reasoning}
                </p>
              </div>

              {/* Suggestions panel */}
              {recommendation.suggestions && recommendation.suggestions.length > 0 && (
                <div className="p-6 rounded-2xl border border-slate-800 bg-slate-900/40 backdrop-blur-xl">
                  <h2 className="text-lg font-bold text-white mb-2">Recommended Adjustments</h2>
                  <p className="text-xs text-slate-400 mb-6">
                    Relaxing these constraints will reveal matching products. We recommend adjusting:
                  </p>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {recommendation.suggestions.map((s, idx) => (
                      <div key={idx} className="p-4 rounded-xl border border-slate-800/80 bg-slate-950/40 flex flex-col gap-2">
                        <span className="text-xs font-bold text-slate-400 uppercase tracking-wide">
                          {s.label}
                        </span>
                        <div className="flex items-center gap-3 mt-1">
                          <span className="text-xs text-rose-400 line-through font-semibold">
                            {s.current}
                          </span>
                          <span className="text-xs text-slate-500 font-bold">&rarr;</span>
                          <span className="text-sm text-emerald-400 font-bold">
                            {s.recommended}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Closest Matches Table */}
              {recommendation.closest_matches && recommendation.closest_matches.length > 0 && (
                <div className="p-6 rounded-2xl border border-slate-800 bg-slate-900/40 backdrop-blur-xl">
                  <h2 className="text-lg font-bold text-white mb-2">Closest Matching Products</h2>
                  <p className="text-xs text-slate-400 mb-6">
                    These products of the correct subtype are extremely close but fail on specific constraints:
                  </p>
                  
                  <div className="flex flex-col gap-4">
                    {recommendation.closest_matches.map((match) => (
                      <div key={match.sku} className="bg-slate-950/50 p-5 rounded-xl border border-slate-850 flex flex-col gap-4">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-900 pb-3">
                          <div>
                            <span className="text-xs text-indigo-400 font-bold uppercase tracking-wider bg-indigo-500/10 px-2 py-0.5 rounded mr-2">
                              Rank #{match.rank}
                            </span>
                            <strong className="text-slate-100 text-base">{match.name}</strong>
                          </div>
                          <span className="text-lg font-black text-white">
                            {recommendation.verdict_product?.symbol || "₹"}{match.price.toLocaleString()}
                          </span>
                        </div>
                        
                        <div className="flex flex-wrap gap-2.5">
                          {match.checks.map((check, cIdx) => (
                            <div
                              key={cIdx}
                              className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 border ${
                                check.status === "pass"
                                  ? "bg-emerald-500/5 border-emerald-500/20 text-emerald-400"
                                  : "bg-rose-500/5 border-rose-500/20 text-rose-400"
                              }`}
                            >
                              <span>
                                {check.status === "pass" ? "✓" : "✗"}
                              </span>
                              <span>
                                {check.label}:
                              </span>
                              <strong className={check.status === "pass" ? "text-emerald-300" : "text-rose-300"}>
                                {check.value}
                              </strong>
                              {check.status === "fail" && check.deviation && (
                                <span className="text-[10px] uppercase font-extrabold px-1.5 py-0.5 bg-rose-500/10 rounded">
                                  {check.deviation}
                                </span>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Collapsible Decision Trace Inspector for Curators */}
              <div className="border border-slate-850 rounded-xl overflow-hidden mt-4">
                <button
                  onClick={() => setShowTrace(!showTrace)}
                  className="w-full px-6 py-4 bg-slate-900/50 flex items-center justify-between text-sm font-bold text-slate-350 hover:bg-slate-900 hover:text-white transition-all"
                >
                  <span>Inspect Mathematical Decision Trace</span>
                  <span>{showTrace ? "Hide Trace &uarr;" : "View Trace &darr;"}</span>
                </button>
                
                {showTrace && (
                  <div className="p-6 bg-slate-950 border-t border-slate-850 text-xs font-mono overflow-auto max-h-[400px]">
                    <h4 className="text-indigo-400 font-bold uppercase mb-2 border-b border-slate-900 pb-1">1. Applied Constraints</h4>
                    <pre className="text-slate-400 mb-6 bg-slate-900/40 p-2.5 rounded">{JSON.stringify(recommendation.decision_trace.applied_constraints, null, 2)}</pre>
                    
                    <h4 className="text-indigo-400 font-bold uppercase mb-2 border-b border-slate-900 pb-1">2. Normalized Attribute Weights</h4>
                    <pre className="text-slate-400 mb-6 bg-slate-900/40 p-2.5 rounded">{JSON.stringify(recommendation.decision_trace.normalized_weights, null, 2)}</pre>

                    <h4 className="text-indigo-400 font-bold uppercase mb-2 border-b border-slate-900 pb-1">3. Scoring Matrix Breakdown</h4>
                    <pre className="text-slate-400 mb-6 bg-slate-900/40 p-2.5 rounded">{JSON.stringify(recommendation.decision_trace.scoring_breakdown, null, 2)}</pre>

                    <h4 className="text-indigo-400 font-bold uppercase mb-2 border-b border-slate-900 pb-1">4. Closest Matches in Trace</h4>
                    <pre className="text-slate-400 bg-slate-900/40 p-2.5 rounded">{JSON.stringify(recommendation.decision_trace.closest_matches, null, 2)}</pre>
                  </div>
                )}
              </div>

            </div>
          </>
        ) : (
          <>
            {/* Left Column: Recommended Product details Card */}
            <div className="lg:col-span-1 flex flex-col gap-6">
              <div className="p-6 rounded-2xl border border-slate-800 bg-slate-900/40 backdrop-blur-xl flex flex-col justify-between relative overflow-hidden">
                <div className="absolute top-0 right-0 w-24 h-24 bg-indigo-500/10 rounded-full blur-2xl pointer-events-none" />
                
                <div>
                  <span className="text-xs font-extrabold uppercase tracking-widest text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 px-2.5 py-1 rounded">
                    Recommended Verdict
                  </span>
                  
                  <h1 className="text-2xl font-bold text-white mt-6 mb-2 leading-snug">
                    {p!.name}
                  </h1>
                  
                  <span className="text-3xl font-black bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
                    {p!.symbol || "$"}{p!.price.toLocaleString()}
                  </span>

                  {/* Product Image */}
                  <div className="my-5 w-full h-44 rounded-xl overflow-hidden border border-slate-800 bg-slate-950/60 relative">
                    <img
                      src={specMap.image_url || "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=500&q=80"}
                      alt={p!.name}
                      className="w-full h-full object-cover"
                    />
                  </div>

                  {/* Dynamic Specs List */}
                  <div className="border-t border-slate-800/80 pt-6 mt-6 flex flex-col gap-3">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">Specifications:</h3>
                    <div className="grid grid-cols-2 gap-3 text-sm">
                      {recommendation.display_specs && recommendation.display_specs.length > 0 ? (
                        recommendation.display_specs.map((spec) => {
                          const val = specMap[spec.key];
                          if (val === undefined || val === null) return null;
                          return (
                            <div key={spec.key} className="bg-slate-950/40 p-2.5 rounded-lg border border-slate-850">
                              <span className="block text-xs text-slate-500">{spec.label}</span>
                              <strong className="text-slate-200">{val}{spec.unit ? ` ${spec.unit}` : ""}</strong>
                            </div>
                          );
                        })
                      ) : (
                        <>
                          <div className="bg-slate-950/40 p-2.5 rounded-lg border border-slate-850">
                            <span className="block text-xs text-slate-500">Memory (RAM)</span>
                            <strong className="text-slate-200">{specMap.ram_gb || "—"} GB</strong>
                          </div>
                          <div className="bg-slate-950/40 p-2.5 rounded-lg border border-slate-850">
                            <span className="block text-xs text-slate-500">Storage</span>
                            <strong className="text-slate-200">{specMap.storage_gb || "—"} GB SSD</strong>
                          </div>
                          <div className="bg-slate-950/40 p-2.5 rounded-lg border border-slate-850">
                            <span className="block text-xs text-slate-500">Battery Life</span>
                            <strong className="text-slate-200">{specMap.battery_hours || "—"} Hours</strong>
                          </div>
                          <div className="bg-slate-950/40 p-2.5 rounded-lg border border-slate-850">
                            <span className="block text-xs text-slate-500">Weight</span>
                            <strong className="text-slate-200">{specMap.weight_kg || "—"} kg</strong>
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                </div>

                {/* Circular Confidence Meter */}
                <div className="mt-8 border-t border-slate-800 pt-6 flex items-center justify-between">
                  <div>
                    <span className="block text-xs font-bold uppercase text-slate-400">Match Confidence</span>
                    <span className="text-slate-500 text-xs">Based on preferences consistency</span>
                  </div>
                  <div className="relative w-16 h-16 flex items-center justify-center">
                    <svg className="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
                      <path
                        className="text-slate-800"
                        strokeWidth="3.5"
                        stroke="currentColor"
                        fill="none"
                        d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                      />
                      <path
                        className="text-indigo-500"
                        strokeDasharray={`${recommendation.confidence}, 100`}
                        strokeWidth="3.5"
                        strokeLinecap="round"
                        stroke="currentColor"
                        fill="none"
                        d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                      />
                    </svg>
                    <div className="absolute text-sm font-black text-white">
                      {Math.round(recommendation.confidence)}%
                    </div>
                  </div>
                </div>

              </div>
            </div>

            {/* Right Column: AI Analysis, Trade-offs Table, and Trace Drawer */}
            <div className="lg:col-span-2 flex flex-col gap-6">
              
              {/* Why Nexus Recommends This (AI Verdict) */}
              <div className="p-8 rounded-2xl border border-indigo-500/20 bg-gradient-to-br from-indigo-950/20 via-slate-900/40 to-purple-950/10 backdrop-blur-xl relative overflow-hidden">
                <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-500/5 rounded-full blur-3xl pointer-events-none" />
                
                <h2 className="text-xl font-extrabold text-white tracking-tight mb-6 flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-indigo-400 animate-pulse" />
                  Why Nexus Recommends This
                </h2>

                <div className="flex flex-col md:flex-row gap-6 items-start">
                  {/* Big Score Badge */}
                  <div className="flex-shrink-0 flex flex-col items-center justify-center p-4 rounded-xl bg-slate-950/60 border border-slate-800/80 w-28 h-28">
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">VERDICT</span>
                    <span className="text-3xl font-black text-indigo-400 mt-1 font-mono">
                      {Math.round(recommendation.score || recommendation.confidence)}
                    </span>
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">/ 100</span>
                  </div>

                  <div className="flex-grow">
                    <p className="text-slate-200 text-base font-semibold leading-relaxed mb-3">
                      This product scored {Math.round(recommendation.score || recommendation.confidence)}/100 for your priorities because {recommendation.summary.replace(/^"|"$/g, '')}
                    </p>
                    <p className="text-slate-400 text-sm leading-relaxed whitespace-pre-wrap">
                      {recommendation.reasoning}
                    </p>
                  </div>
                </div>
              </div>

              {/* Pros and Cons bullet columns */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="p-6 rounded-2xl border border-emerald-950/40 bg-emerald-500/5 backdrop-blur-xl">
                  <h3 className="text-sm font-bold uppercase tracking-wider text-emerald-400 mb-4 flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-emerald-400" /> Key Strengths
                  </h3>
                  <ul className="flex flex-col gap-3">
                    {recommendation.pros.map((pro, i) => (
                      <li key={i} className="text-slate-300 text-xs flex gap-2 leading-relaxed">
                        <span className="text-emerald-500 font-bold">✓</span>
                        {pro}
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="p-6 rounded-2xl border border-rose-950/40 bg-rose-500/5 backdrop-blur-xl">
                  <h3 className="text-sm font-bold uppercase tracking-wider text-rose-400 mb-4 flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-rose-400" /> Drawbacks / Limitations
                  </h3>
                  <ul className="flex flex-col gap-3">
                    {recommendation.cons.map((con, i) => (
                      <li key={i} className="text-slate-300 text-xs flex gap-2 leading-relaxed">
                        <span className="text-rose-500 font-bold">×</span>
                        {con}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Trade-offs Comparisons with alternatives */}
              {recommendation.tradeoffs && recommendation.tradeoffs.length > 0 && (
                <div className="p-6 rounded-2xl border border-slate-800 bg-slate-900/40 backdrop-blur-xl">
                  <h2 className="text-lg font-bold text-white mb-4">Alternatives & Spec Trade-offs</h2>
                  <p className="text-xs text-slate-400 mb-4">
                    How does the winning product compare against secondary options? Click on any alternative to view its full details.
                  </p>
                  
                  <div className="flex flex-col gap-4">
                    {recommendation.tradeoffs.map((t, idx) => (
                      <div 
                        key={idx} 
                        onClick={() => setSelectedAlt(t)}
                        className="bg-slate-950/50 p-4 rounded-xl border border-slate-850 flex flex-col gap-3 cursor-pointer hover:bg-slate-900/40 hover:border-indigo-500/30 transition-all group animate-fadeIn"
                      >
                        <div className="flex items-center justify-between">
                          <strong className="text-slate-250 text-sm group-hover:text-indigo-400 transition-colors">{t.alternative_name}</strong>
                          <div className="flex items-center gap-2">
                            <span className="text-[10px] text-slate-500 font-semibold group-hover:text-slate-300 transition-colors">View Details &rarr;</span>
                            <span className="text-xs font-bold text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded">
                              Score: {Math.round(t.alternative_score * 100)}%
                            </span>
                          </div>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
                          {t.deltas.map((d: any, dIdx: number) => (
                            <div key={dIdx} className="flex items-center justify-between border-b border-slate-900/50 pb-1.5">
                              <span className="text-slate-500">{d.attribute}</span>
                              <span className={`font-semibold ${
                                d.direction === "better" ? "text-emerald-400" : "text-rose-400"
                              }`}>
                                {d.description}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Verified Citations links */}
              {recommendation.citations && recommendation.citations.length > 0 && (
                <div className="px-6 py-4 rounded-xl border border-slate-850/60 bg-slate-900/10 text-xs flex items-center justify-between gap-4">
                  <span className="font-bold text-slate-500 uppercase tracking-wider">Verified Sources:</span>
                  <div className="flex gap-4">
                    {recommendation.citations.map((cite, idx) => (
                      <span key={idx} className="text-slate-400 select-all hover:text-white transition-all cursor-copy">
                        {cite}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Collapsible Decision Trace Inspector for Curators */}
              <div className="border border-slate-850 rounded-xl overflow-hidden mt-4">
                <button
                  onClick={() => setShowTrace(!showTrace)}
                  className="w-full px-6 py-4 bg-slate-900/50 flex items-center justify-between text-sm font-bold text-slate-350 hover:bg-slate-900 hover:text-white transition-all"
                >
                  <span>Inspect Mathematical Decision Trace</span>
                  <span>{showTrace ? "Hide Trace &uarr;" : "View Trace &darr;"}</span>
                </button>
                
                {showTrace && (
                  <div className="p-6 bg-slate-950 border-t border-slate-850 text-xs font-mono overflow-auto max-h-[400px]">
                    <h4 className="text-indigo-400 font-bold uppercase mb-2 border-b border-slate-900 pb-1">1. Applied Constraints</h4>
                    <pre className="text-slate-400 mb-6 bg-slate-900/40 p-2.5 rounded">{JSON.stringify(recommendation.decision_trace.applied_constraints, null, 2)}</pre>
                    
                    <h4 className="text-indigo-400 font-bold uppercase mb-2 border-b border-slate-900 pb-1">2. Normalized Attribute Weights</h4>
                    <pre className="text-slate-400 mb-6 bg-slate-900/40 p-2.5 rounded">{JSON.stringify(recommendation.decision_trace.normalized_weights, null, 2)}</pre>

                    <h4 className="text-indigo-400 font-bold uppercase mb-2 border-b border-slate-900 pb-1">3. Scoring Matrix Breakdown</h4>
                    <pre className="text-slate-400 mb-6 bg-slate-900/40 p-2.5 rounded">{JSON.stringify(recommendation.decision_trace.scoring_breakdown, null, 2)}</pre>

                    <h4 className="text-indigo-400 font-bold uppercase mb-2 border-b border-slate-900 pb-1">4. Final Ranking Results</h4>
                    <pre className="text-slate-400 bg-slate-900/40 p-2.5 rounded">{JSON.stringify(recommendation.decision_trace.ranking, null, 2)}</pre>
                  </div>
                )}
              </div>

            </div>
          </>
        )}
      </main>

      {/* Alternative Details Modal */}
      {selectedAlt && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md flex items-center justify-center z-50 p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl relative overflow-hidden flex flex-col gap-6 max-h-[90vh]">
            <div className="absolute top-0 right-0 w-24 h-24 bg-indigo-500/5 rounded-full blur-2xl pointer-events-none" />
            
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[10px] font-extrabold uppercase tracking-widest text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 px-2.5 py-1 rounded">
                  Alternative Match ({Math.round(selectedAlt.alternative_score * 100)}% Score)
                </span>
                <h2 className="text-xl font-bold text-white mt-3">{selectedAlt.alternative_name}</h2>
                {selectedAlt.alternative_price && (
                  <span className="text-2xl font-black text-slate-200 mt-1 block">
                    {recommendation.verdict_product?.symbol || "₹"}{selectedAlt.alternative_price.toLocaleString()}
                  </span>
                )}
              </div>
              <button 
                onClick={() => setSelectedAlt(null)}
                className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-850 transition-all text-xl font-bold leading-none"
              >
                ×
              </button>
            </div>

            {/* Product Image */}
            <div className="w-full h-40 rounded-xl overflow-hidden border border-slate-800 bg-slate-950/60 relative">
              <img
                src={selectedAlt.alternative_specs?.image_url || "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=500&q=80"}
                alt={selectedAlt.alternative_name}
                className="w-full h-full object-cover"
              />
            </div>

            {/* Specifications */}
            <div className="flex flex-col gap-3 overflow-y-auto pr-1 max-h-[250px]">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">Specifications:</h3>
              <div className="grid grid-cols-2 gap-3 text-sm">
                {recommendation.display_specs && recommendation.display_specs.length > 0 ? (
                  recommendation.display_specs.map((spec) => {
                    const val = selectedAlt.alternative_specs?.[spec.key];
                    if (val === undefined || val === null) return null;
                    return (
                      <div key={spec.key} className="bg-slate-950/40 p-2.5 rounded-lg border border-slate-850">
                        <span className="block text-xs text-slate-500">{spec.label}</span>
                        <strong className="text-slate-200">{val}{spec.unit ? ` ${spec.unit}` : ""}</strong>
                      </div>
                    );
                  })
                ) : (
                  Object.entries(selectedAlt.alternative_specs || {}).map(([key, val]) => {
                    if (key === "image_url" || typeof val === "object") return null;
                    return (
                      <div key={key} className="bg-slate-950/40 p-2.5 rounded-lg border border-slate-850">
                        <span className="block text-xs text-slate-500 capitalize">{key.replace('_', ' ')}</span>
                        <strong className="text-slate-200">{String(val)}</strong>
                      </div>
                    );
                  })
                )}
              </div>
            </div>

            {/* Comparison Deltas */}
            <div className="border-t border-slate-800/80 pt-4 flex flex-col gap-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">Comparison to Winner:</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                {selectedAlt.deltas.map((d: any, dIdx: number) => (
                  <div key={dIdx} className="flex items-center justify-between border-b border-slate-800 pb-1.5">
                    <span className="text-slate-500">{d.attribute}</span>
                    <span className={`font-semibold ${
                      d.direction === "better" ? "text-emerald-400" : "text-rose-400"
                    }`}>
                      {d.description}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <button 
              onClick={() => setSelectedAlt(null)}
              className="w-full py-2.5 bg-slate-800 hover:bg-slate-750 text-slate-200 rounded-xl text-sm font-semibold transition-all border border-slate-750"
            >
              Close Details
            </button>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="py-6 border-t border-slate-900 text-center text-xs text-slate-650 bg-slate-950/20 backdrop-blur-sm mt-12">
        Data parsed and scored via the Nexus category-agnostic MCDA execution runtime.
      </footer>
    </div>
  );
}
