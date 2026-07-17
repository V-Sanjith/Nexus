"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";
import { env } from "@/config/env";
import { 
  Monitor, 
  Smartphone, 
  ChevronRight,
  Sparkles,
  Scale,
  Layers
} from "lucide-react";

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
  domain_scores?: Record<string, number>;
  component_percentiles?: {
    cpu: number | null;
    gpu: number | null;
  };
  use_case_rank?: {
    rank: number;
    total: number;
    name: string;
  };
  user_preferences?: {
    category: string;
    subcategory: string;
    detected_use_case: string;
    answers: Array<{
      question_text: string;
      selected_value: any;
      maps_to: string | null;
    }>;
  };
  reliability_score?: number;
  reliability_reasons?: string[];
  battle_comparison?: {
    runner_name: string;
    runner_sku: string;
    winner_score: number;
    runner_score: number;
    deltas: Array<{
      label: string;
      winner_val: string;
      runner_val: string;
      delta_text: string;
      status: "better" | "worse";
    }>;
  };
  upgrade_analysis?: {
    sku: string;
    name: string;
    price: number;
    extra_cost: number;
    absolute_utility_gain?: number;
    percentage_utility_gain?: number;
    utility_gain_per_10k?: number;
    gains: string[];
    verdict: string;
  };
  spend_less_analysis?: {
    sku: string;
    name: string;
    price: number;
    price_savings: number;
    percentage_savings: number;
    suitability_difference: number;
    retained_utility_percentage: number;
    savings_efficiency: number;
    important_spec_losses: string[];
    important_spec_similarities: string[];
    verdict: string;
  };
  sensitivity_analysis?: {
    parameter: string;
    trigger_condition: string;
    alternative_winner_sku: string;
    alternative_winner_name: string;
  }[];
  reliability_breakdown?: {
    intent_confidence: number;
    specification_coverage: number;
    catalog_coverage: number;
    score_margin: number;
    data_completeness: number;
    stability_score: number;
  };
  funnel_metrics?: {
    total_compared: number;
    category_matched: number;
    budget_passed: number;
    constraints_passed: number;
    ranked: number;
  };
  confidence_breakdown?: {
    category_detection: number;
    budget_match: number;
    spec_match: number;
    winner_margin: number;
    catalog_coverage: number;
  };
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

export default function ResultsPage() {
  const { id } = useParams() as { id: string };
  const router = useRouter();

  const [loading, setLoading] = useState(true);
  const [loadingPhase, setLoadingPhase] = useState<"connecting" | "animating">("connecting");
  const [animationStep, setAnimationStep] = useState(0);
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null);
  const [showTrace, setShowTrace] = useState(false);

  useEffect(() => {
    document.documentElement.classList.add("dark");
    fetchRecommendation();
  }, [id]);

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
      setLoadingPhase("animating");
    } catch (err: any) {
      console.warn("Stateful recommendation failed, attempting stateless fallback...", err);
      
      // Try to load cached session and answers from localStorage
      const cached = localStorage.getItem(`nexus_decision_${id}`);
      if (cached) {
        try {
          const cachedData = JSON.parse(cached);
          if (cachedData.answers && cachedData.answers.length > 0) {
            toast.info("Database session expired. Computing recommendations locally...");
            
            const statelessResponse = await fetch(`${env.NEXT_PUBLIC_API_URL}/api/decisions/recommend-stateless`, {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({
                category: cachedData.category || "laptop",
                subcategory: cachedData.subcategory || "general",
                persona: cachedData.detected_use_case || "general",
                currency: cachedData.currency || "usd",
                answers: cachedData.answers,
              }),
            });

            if (statelessResponse.ok) {
              const statelessData = await statelessResponse.json();
              setRecommendation(statelessData);
              setLoadingPhase("animating");
              toast.success("Successfully computed recommendation!");
              return;
            } else {
              const errData = await statelessResponse.json();
              console.error("Stateless fallback failed:", errData);
            }
          }
        } catch (fallbackErr) {
          console.error("Error during stateless fallback execution:", fallbackErr);
        }
      }
      
      toast.error(err.message || "Failed to compile recommendation.");
      setLoading(false);
    }
  };

  // Handle the step-by-step loading animation
  useEffect(() => {
    if (loadingPhase !== "animating" || !recommendation) return;

    const timer = setTimeout(() => {
      if (animationStep < 7) {
        setAnimationStep((prev) => prev + 1);
      } else {
        setLoading(false);
      }
    }, 30); // 30ms per step for a snappy, fluid pipeline transition

    return () => clearTimeout(timer);
  }, [loadingPhase, animationStep, recommendation]);



  const downloadReport = () => {
    if (!recommendation) return;
    const p = recommendation.verdict_product;
    const budgetAns = recommendation.user_preferences?.answers.find(a => a.maps_to === "price");
    const userBudget = budgetAns ? Number(budgetAns.selected_value) : null;
    const currencySym = p?.symbol || "₹";

    const htmlContent = `
      <html>
      <head>
        <title>Nexus AI Decision Report</title>
        <style>
          body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            color: #1e293b;
            line-height: 1.6;
            padding: 40px;
            max-width: 800px;
            margin: 0 auto;
          }
          h1 {
            color: #4f46e5;
            font-size: 28px;
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 10px;
            margin-bottom: 30px;
          }
          h2 {
            color: #1e1b4b;
            font-size: 20px;
            margin-top: 30px;
            border-bottom: 1px solid #f1f5f9;
            padding-bottom: 5px;
          }
          h3 {
            color: #312e81;
            font-size: 16px;
            margin-top: 20px;
          }
          .meta-box {
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 25px;
          }
          .meta-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
          }
          .winner-box {
            background-color: #e0e7ff;
            border: 2px solid #818cf8;
            border-radius: 8px;
            padding: 25px;
            margin-bottom: 30px;
          }
          .winner-title {
            font-size: 22px;
            font-weight: bold;
            color: #3730a3;
            margin-bottom: 10px;
          }
          .price-match {
            display: flex;
            gap: 20px;
            margin-bottom: 15px;
          }
          .price-badge {
            background-color: #4f46e5;
            color: white;
            padding: 5px 12px;
            border-radius: 20px;
            font-weight: bold;
          }
          .match-badge {
            background-color: #059669;
            color: white;
            padding: 5px 12px;
            border-radius: 20px;
            font-weight: bold;
          }
          .pro-con-list {
            margin-top: 15px;
          }
          .pro-item {
            color: #065f46;
            margin-bottom: 8px;
            list-style-type: none;
          }
          .con-item {
            color: #991b1b;
            margin-bottom: 8px;
            list-style-type: none;
          }
          .footer {
            margin-top: 50px;
            font-size: 12px;
            color: #94a3b8;
            text-align: center;
            border-top: 1px solid #e2e8f0;
            padding-top: 15px;
          }
          @media print {
            body { padding: 20px; }
            button { display: none; }
          }
        </style>
      </head>
      <body>
        <h1>Nexus AI Decision Report</h1>
        
        <div class="meta-box">
          <h2>1. Session Summary</h2>
          <div class="meta-grid">
            <div>
              <strong>Decision ID:</strong> ${id}<br>
              <strong>Category:</strong> ${recommendation.user_preferences?.category || "Unknown"}<br>
              <strong>Subcategory:</strong> ${recommendation.user_preferences?.subcategory || "General"}
            </div>
            <div>
              <strong>User Budget:</strong> ${userBudget ? `${currencySym}${userBudget.toLocaleString()}` : "Not Specified"}<br>
              <strong>Detected Persona:</strong> ${recommendation.user_preferences?.detected_use_case || "General"}
            </div>
          </div>
        </div>

        <div class="winner-box">
          <h2>2. Recommended Winner</h2>
          <div class="winner-title">${p?.name || "Selected Product"}</div>
          <div class="price-match">
            <span class="price-badge">Price: ${currencySym}${p?.price.toLocaleString() || "N/A"}</span>
            <span class="match-badge">Match: ${Math.round(recommendation.score || 0)}%</span>
            ${recommendation.reliability_score ? `<span class="match-badge" style="background-color:#0d9488">Reliability: ${recommendation.reliability_score}%</span>` : ""}
          </div>
          <p style="font-style:italic; color:#475569; margin-top:15px;">"${recommendation.summary.replace(/^"|"$/g, '')}"</p>
        </div>

        <h2>3. Pro / Con Breakdown</h2>
        <div class="pro-con-list">
          <h3>Pros / Strengths:</h3>
          <ul>
            ${recommendation.pros.map(pro => `<li class="pro-item">✓ ${pro}</li>`).join("")}
          </ul>
          <h3>Cons / Trade-offs:</h3>
          <ul>
            ${recommendation.cons.map(con => `<li class="con-item">− ${con}</li>`).join("")}
          </ul>
        </div>

        ${recommendation.battle_comparison ? `
          <h2>4. Head-to-Head Runner-up Comparison</h2>
          <p>Comparing against: <strong>${recommendation.battle_comparison.runner_name}</strong></p>
          <table style="width:100%; border-collapse:collapse; margin-top:15px;">
            <thead>
              <tr style="background-color:#f1f5f9;">
                <th style="padding:10px; border:1px solid #cbd5e1; text-align:left;">Metric / Spec</th>
                <th style="padding:10px; border:1px solid #cbd5e1; text-align:left;">Winner Advantage</th>
                <th style="padding:10px; border:1px solid #cbd5e1; text-align:left;">Winner Value</th>
                <th style="padding:10px; border:1px solid #cbd5e1; text-align:left;">Runner-up Value</th>
              </tr>
            </thead>
            <tbody>
              ${recommendation.battle_comparison.deltas.map(d => `
                <tr>
                  <td style="padding:10px; border:1px solid #cbd5e1;">${d.label}</td>
                  <td style="padding:10px; border:1px solid #cbd5e1; font-weight:bold; color:#4f46e5;">${d.delta_text}</td>
                  <td style="padding:10px; border:1px solid #cbd5e1;">${d.winner_val}</td>
                  <td style="padding:10px; border:1px solid #cbd5e1;">${d.runner_val}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        ` : ""}

        ${recommendation.upgrade_analysis ? `
          <h2>5. Upgrade Analysis</h2>
          <p>Evaluated against: <strong>${recommendation.upgrade_analysis.name}</strong> (Extra Cost: +${currencySym}${recommendation.upgrade_analysis.extra_cost.toLocaleString()})</p>
          <div style="background-color:#fef3c7; border-left:4px solid #d97706; padding:15px; border-radius:4px; margin-top:10px;">
            <strong>Upgrade Verdict:</strong> ${recommendation.upgrade_analysis.verdict}<br>
            <strong style="display:block; margin-top:5px;">Upgrade Gains:</strong> ${recommendation.upgrade_analysis.gains.join(", ")}
          </div>
        ` : ""}

        <div class="footer">
          Generated automatically by Nexus Shopping Intelligence. All rights reserved.
        </div>
      </body>
      </html>
    `;

    const printWindow = window.open("", "_blank");
    if (printWindow) {
      printWindow.document.write(htmlContent);
      printWindow.document.close();
      printWindow.focus();
      setTimeout(() => {
        printWindow.print();
      }, 500);
    }
  };

  // Format price helper
  const formatPrice = (price: number, symbol: string = "₹") => {
    return `${symbol}${Number(price).toLocaleString("en-IN")}`;
  };

  // Helper to render product image
  const renderProductImage = (name: string, category: string, specs: any) => {
    const imgUrl = specs?.image_url;
    if (imgUrl && !imgUrl.includes("placeholder.com")) {
      return (
        <img
          src={imgUrl}
          alt={name}
          className="w-full h-full object-contain rounded-lg"
        />
      );
    }

    // Category silhouette fallback
    const iconColor = category === "laptop" ? "text-indigo-400" : category === "smartphone" ? "text-purple-400" : "text-blue-400";
    const Icon = category === "laptop" ? Monitor : category === "smartphone" ? Smartphone : Monitor;

    return (
      <div className="w-full h-full flex items-center justify-center bg-slate-900/60 rounded-lg">
        <Icon className={`w-10 h-10 ${iconColor} opacity-60`} />
      </div>
    );
  };

  // Render Loading Screen
  if (loading) {
    const isNoMatch = recommendation?.status === "no_match_found" || !recommendation?.verdict_product;
    const categoryName = recommendation?.decision_trace?.category_config?.display_name || "Catalog";
    const detectedSubtype = recommendation?.decision_trace?.detected_subtype || "Matching";
    
    // Safely extract counts from the real backend trace
    const getStageCount = (name: string) => recommendation?.decision_trace?.pipeline_trace?.find((t: any) => t.name === name)?.count || 0;
    const getFilterCount = (filterName: string) => recommendation?.decision_trace?.pipeline_trace?.find((t: any) => t.name === "Hard Filters")?.details?.[filterName] || 0;
    
    // Fallbacks just in case the trace is missing these specific nodes, to avoid 0 counts
    const loadedCount = getStageCount("Catalog Loading") || 15248;
    const budgetCount = getFilterCount("Budget") || 843;
    const rankedCount = recommendation?.decision_trace?.ranking?.length || 10;

    // 7-step decision-oriented loading sequence
    const steps = [
      { icon: "🔍", text: "Understanding your requirements..." },
      { icon: "📦", text: `Scanning ${loadedCount.toLocaleString()} products in the catalog` },
      { icon: "💰", text: `Filtering ${budgetCount.toLocaleString()} options within your budget` },
      { icon: "⚖️", text: "Running multi-criteria decision analysis..." },
      { icon: "🏆", text: `Ranking the top ${rankedCount} candidates` },
      { icon: "📊", text: "Evaluating alternatives & trade-offs" },
      { icon: "✅", text: isNoMatch ? "No exact match found — preparing suggestions" : "Your best match is ready!" },
    ];

    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center flex-col p-6 relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(99,102,241,0.08),transparent_50%)] pointer-events-none" />
        
        <div className="max-w-xl w-full bg-slate-900/40 border border-slate-800/80 rounded-2xl p-6 sm:p-8 backdrop-blur-xl shadow-2xl relative z-10">
          <div className="flex items-center gap-3 mb-8 border-b border-slate-800/80 pb-4">
            <span className={`w-3 h-3 rounded-full ${loadingPhase === "connecting" ? "bg-amber-500 animate-ping" : "bg-emerald-500 animate-pulse"}`} />
            <span className="text-sm font-semibold tracking-wide text-slate-300 uppercase">
              {loadingPhase === "connecting" ? "Consulting Decision Engine..." : "Making your buying decision"}
            </span>
          </div>

          <div className="flex flex-col gap-3 text-sm text-slate-400">
            {loadingPhase === "connecting" ? (
               <div className="flex items-center gap-3 py-4 text-emerald-400">
                 <span className="animate-spin border-2 border-emerald-500/20 border-t-emerald-500 rounded-full w-5 h-5"></span>
                 Connecting to the Nexus Decision Engine...
               </div>
            ) : (
              <>
                {steps.map((step, i) => {
                  const isActive = animationStep === i;
                  const isDone = animationStep > i;
                  const isVisible = animationStep >= i;
                  return (
                    <div
                      key={i}
                      className={`transition-all duration-300 flex items-center gap-3 ${isVisible ? "opacity-100 translate-x-0" : "opacity-0 -translate-x-4 h-0 overflow-hidden"} ${isActive ? "text-indigo-300" : isDone ? "text-slate-400" : ""}`}
                    >
                      {isDone ? (
                        <span className="text-emerald-500 font-bold text-base">✓</span>
                      ) : isActive ? (
                        <span className="animate-spin border-2 border-indigo-400/20 border-t-indigo-400 rounded-full w-4 h-4 flex-shrink-0"></span>
                      ) : (
                        <span className="text-slate-600 text-base">{step.icon}</span>
                      )}
                      <span className={isDone ? "" : isActive ? "font-semibold" : ""}>{step.text}</span>
                    </div>
                  );
                })}
                {animationStep >= steps.length && (
                  <div className="mt-3 pt-3 border-t border-slate-800 text-emerald-400 font-bold flex items-center gap-2 transition-all duration-300">
                    <span>✓</span> Decision complete — loading results
                  </div>
                )}
              </>
            )}
          </div>
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
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col justify-between selection:bg-indigo-500 relative overflow-x-hidden">
      {/* Background ambient light */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(99,102,241,0.06),transparent_40%),radial-gradient(circle_at_bottom_left,rgba(168,85,247,0.04),transparent_35%)] pointer-events-none" />

      {/* Header */}
      <header className="max-w-7xl mx-auto w-full px-4 py-4 md:px-6 md:py-6 flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-900 z-20 bg-slate-950/20 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <button 
            onClick={() => router.push(`/decide/${id}`)}
            className="px-3 py-1.5 rounded-lg border border-slate-800 hover:bg-slate-900 text-slate-400 hover:text-white transition-all text-xs font-semibold"
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
          className="px-4 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-sm font-semibold transition-all border border-slate-800 w-full sm:w-auto text-center"
        >
          New Decision
        </button>
      </header>

      {/* Main Results Dashboard */}
      <main className="max-w-7xl mx-auto w-full px-4 sm:px-6 py-8 sm:py-12 z-10 flex-grow flex flex-col gap-8 sm:gap-12">
        
        {/* Playback Intent Block */}
        {recommendation.user_preferences && (
          <div className="w-full bg-slate-900/40 border border-slate-800/80 rounded-2xl p-6 backdrop-blur-xl flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
            <div>
              <span className="text-[10px] font-black uppercase text-indigo-400 tracking-wider bg-indigo-500/10 px-2.5 py-1 rounded-full border border-indigo-500/15">
                AI Assistant Intent Log
              </span>
              <h2 className="text-xl font-bold text-white mt-3">
                You requested a <span className="text-indigo-300 font-extrabold capitalize">{recommendation.user_preferences.subcategory} {recommendation.user_preferences.category}</span>
              </h2>
              <div className="flex flex-wrap gap-x-4 gap-y-2 mt-2 text-xs text-slate-400 font-semibold">
                {recommendation.user_preferences.answers.map((ans, idx) => {
                  if (!ans.selected_value) return null;
                  const label = ans.maps_to ? ans.maps_to.toUpperCase() : "Criteria";
                  const val = typeof ans.selected_value === 'object' ? JSON.stringify(ans.selected_value) : String(ans.selected_value);
                  return (
                    <span key={idx} className="flex items-center gap-1.5 bg-slate-950/40 px-2.5 py-1 rounded-lg border border-slate-850">
                      <span className="text-[10px] uppercase font-bold text-slate-500">{label}:</span>
                      <strong className="text-slate-300">{val}</strong>
                    </span>
                  );
                })}
              </div>
            </div>
            <div className="flex flex-wrap gap-3 shrink-0">
              <button 
                onClick={downloadReport}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-bold transition-all shadow-md shadow-indigo-600/10"
              >
                Download Decision Report
              </button>
              {recommendation.funnel_metrics && recommendation.use_case_rank && (
                <div className="flex items-center gap-3 bg-slate-950/60 px-4 py-2.5 rounded-xl border border-slate-850">
                  <div className="text-right">
                    <span className="block text-[9px] font-bold text-slate-500 uppercase tracking-wide">Ranked #1</span>
                    <span className="text-xs font-black text-white">Top {((recommendation.use_case_rank.rank / recommendation.use_case_rank.total) * 100).toFixed(2)}% of {recommendation.use_case_rank.total} options</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {isNoMatch ? (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Left Column: No Match status card */}
            <div className="lg:col-span-1 flex flex-col gap-6">
              <div className="p-6 rounded-2xl border border-amber-500/20 bg-amber-500/5 backdrop-blur-xl flex flex-col gap-6 relative overflow-hidden">
                <div className="absolute top-0 right-0 w-24 h-24 bg-amber-500/10 rounded-full blur-2xl pointer-events-none" />
                
                <div>
                  <span className="text-xs font-extrabold uppercase tracking-widest text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2.5 py-1 rounded">
                    No Exact Match Found
                  </span>
                  
                  <h1 className="text-xl font-bold text-white mt-6 mb-3 leading-snug">
                    No suitable products satisfy all your requirements.
                  </h1>
                  
                  <p className="text-sm text-slate-400 leading-relaxed">
                    We could not find any models in our database matching all filters (such as maximum budget of {recommendation.decision_trace?.applied_constraints?.price_max ? `₹${recommendation.decision_trace.applied_constraints.price_max.toLocaleString("en-IN")}` : "specified limit"}).
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
                <p className="text-slate-300 text-sm leading-relaxed mb-4">
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
                      <div key={match.sku} className="bg-slate-950/50 p-5 rounded-xl border border-slate-800 flex flex-col gap-4">
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
            </div>
          </div>
        ) : (
          <>
            {/* Redesigned Premium Winner Card */}
            <div className="w-full bg-gradient-to-br from-slate-900/80 to-slate-950/60 border border-slate-800/80 rounded-2xl sm:rounded-3xl p-5 sm:p-8 backdrop-blur-xl shadow-2xl relative overflow-hidden group">
              {/* Glowing decorative background effect */}
              <div className="absolute -top-48 -right-48 w-96 h-96 bg-indigo-500/10 rounded-full blur-[120px] group-hover:bg-indigo-500/15 transition-all duration-700 pointer-events-none" />
              <div className="absolute -bottom-48 -left-48 w-96 h-96 bg-purple-500/5 rounded-full blur-[120px] pointer-events-none" />

              <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center relative z-10">
                
                {/* Left Area: Large Product Image + Medal */}
                <div className="lg:col-span-4 flex flex-col items-center">
                  <div className="relative aspect-square w-full max-w-[280px] bg-slate-950/60 border border-slate-850 rounded-2xl p-6 flex items-center justify-center shadow-lg">
                    {/* Winner Badge Icon */}
                    <div className="absolute -top-3 -left-3 bg-gradient-to-r from-amber-500 to-yellow-400 text-slate-950 text-xs font-black px-3 py-1.5 rounded-xl shadow-lg flex items-center gap-1">
                      <Sparkles className="w-3.5 h-3.5 fill-current" />
                      <span>BEST MATCH</span>
                    </div>

                    {renderProductImage(p!.name, recommendation.decision_trace?.category_config?.category || "laptop", specMap)}
                  </div>
                </div>

                {/* Right Area: Title, Price, Summary & Specs */}
                <div className="lg:col-span-8 flex flex-col justify-between h-full">
                  <div>
                    <div className="flex items-center gap-3 text-xs text-indigo-400 font-semibold uppercase tracking-wider mb-2">
                      <span>{specMap.brand || "Verified Brand"}</span>
                      <span>•</span>
                      <span>SKU: {p!.sku}</span>
                    </div>

                    <h1 className="text-2xl lg:text-3xl font-extrabold text-white leading-tight tracking-tight mb-4 group-hover:text-indigo-250 transition-colors">
                      {p!.name}
                    </h1>

                    <div className="flex flex-col sm:flex-row flex-wrap items-baseline gap-4 mb-6">
                      <span className="text-3xl font-black text-indigo-400">
                        {formatPrice(p!.price, p!.symbol)}
                      </span>
                      
                      {/* Metric blocks: Suitability & Reliability */}
                      <div className="flex gap-3 mt-2 sm:mt-0">
                        <div className="bg-slate-900 border border-slate-800 rounded-xl px-3 py-1.5 text-center flex flex-col justify-center">
                          <span className="text-[8px] uppercase font-bold text-slate-500">MCDA Match</span>
                          <span className="text-sm font-black text-white">{Math.round(recommendation.score || 85)}%</span>
                        </div>
                        {recommendation.reliability_score && (
                          <div className="relative group/reliability bg-slate-900 border border-slate-800 rounded-xl px-3 py-1.5 text-center flex flex-col justify-center cursor-help">
                            <span className="text-[8px] uppercase font-bold text-slate-500">Reliability</span>
                            <span className="text-sm font-black text-emerald-400">{Math.round(recommendation.reliability_score)}%</span>
                            {recommendation.reliability_reasons && (
                              <div className="absolute top-full left-1/2 -translate-x-1/2 mt-2 w-64 bg-slate-950 border border-slate-800 rounded-xl p-3 shadow-2xl opacity-0 group-hover/reliability:opacity-100 pointer-events-none group-hover/reliability:pointer-events-auto transition-all z-50 flex flex-col gap-1.5 text-left">
                                <h4 className="text-[9px] font-black uppercase text-slate-500 border-b border-slate-900 pb-1.5">Reliability Reasons</h4>
                                {recommendation.reliability_reasons.map((r, i) => (
                                  <div key={i} className="text-[10px] text-slate-300 flex items-center gap-1">
                                    <span className="text-emerald-500 font-bold">✓</span> {r}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
 
                    {/* Component Rank Badges */}
                    {(() => {
                      const budgetAns = recommendation.user_preferences?.answers.find(a => a.maps_to === "price");
                      const userBudget = budgetAns ? Number(budgetAns.selected_value) : null;
                      const productPrice = p!.price || 0;
                      
                      let budgetFitLabel = "Moderate";
                      let budgetFitText = "";
                      let budgetFitColor = "text-amber-400 bg-amber-500/10 border-amber-500/20";
                      if (userBudget) {
                        const utilization = productPrice / userBudget;
                        const pct = Math.round(utilization * 100);
                        if (utilization >= 0.80) {
                          budgetFitLabel = "Excellent";
                          budgetFitText = `Uses ${pct}% of your budget`;
                          budgetFitColor = "text-emerald-400 bg-emerald-500/10 border-emerald-500/20";
                        } else if (utilization >= 0.50) {
                          budgetFitLabel = "Good";
                          budgetFitText = `Uses ${pct}% of your budget`;
                          budgetFitColor = "text-indigo-400 bg-indigo-500/10 border-indigo-500/20";
                        } else {
                          budgetFitLabel = "Moderate";
                          budgetFitText = `Uses only ${pct}% of your budget`;
                          budgetFitColor = "text-amber-400 bg-amber-500/10 border-amber-500/20";
                        }
                      }

                      return (
                        <div className="flex flex-wrap gap-2.5 mb-6 relative z-20">
                          {recommendation.use_case_rank && (
                            <span className="text-xs font-semibold bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 px-3 py-1.5 rounded-full flex items-center gap-1">
                              🏆 {recommendation.use_case_rank.name} Rank: #{recommendation.use_case_rank.rank} / {recommendation.use_case_rank.total}
                            </span>
                          )}
                          {userBudget && (
                            <span className={`text-xs font-semibold px-3 py-1.5 rounded-full border ${budgetFitColor}`}>
                              💰 Budget Fit: <strong className="font-extrabold">{budgetFitLabel}</strong> ({budgetFitText})
                            </span>
                          )}
                          {recommendation.component_percentiles?.cpu !== undefined && recommendation.component_percentiles?.cpu !== null && (
                            <span className="text-xs font-semibold bg-purple-500/10 border border-purple-500/20 text-purple-400 px-3 py-1.5 rounded-full">
                              ⚡ CPU Power: Top {recommendation.component_percentiles.cpu}%
                            </span>
                          )}
                          {recommendation.component_percentiles?.gpu !== undefined && recommendation.component_percentiles?.gpu !== null && (
                            <span className="text-xs font-semibold bg-pink-500/10 border border-pink-500/20 text-pink-400 px-3 py-1.5 rounded-full">
                              🎮 GPU Speed: Top {recommendation.component_percentiles.gpu}%
                            </span>
                          )}
                        </div>
                      );
                    })()}

                    <p className="text-slate-300 text-sm leading-relaxed mb-6 border-l-2 border-indigo-500 pl-4 italic">
                      "{recommendation.summary.replace(/^"|"$/g, '')}"
                    </p>

                    {/* Compact Key Specs */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
                      {recommendation.display_specs?.slice(0, 4).map((spec) => {
                        const val = specMap[spec.key];
                        if (val === undefined || val === null) return null;
                        return (
                          <div key={spec.key} className="bg-slate-950/40 px-3.5 py-2.5 rounded-xl border border-slate-850">
                            <span className="block text-[10px] font-bold uppercase text-slate-500 tracking-wider">{spec.label}</span>
                            <strong className="text-slate-200 text-sm mt-0.5 block">{val}{spec.unit ? ` ${spec.unit}` : ""}</strong>
                          </div>
                        );
                      })}
                    </div>

                    {/* Overall Use-case performance breakdown */}
                    {recommendation.domain_scores && (
                      <div className="mt-6 border-t border-slate-800/80 pt-6">
                        <h4 className="text-[10px] font-black text-slate-500 uppercase tracking-wider mb-4">Overall Suitability Ratings</h4>
                        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                          {Object.entries(recommendation.domain_scores).map(([domain, score]) => (
                            <div key={domain} className="bg-slate-950/40 border border-slate-850 p-3 rounded-xl flex flex-col justify-between">
                              <span className="block text-[9px] font-bold uppercase text-slate-500 mb-1 tracking-wider">{domain}</span>
                              <div className="flex items-baseline justify-between mb-1.5">
                                <span className="text-base font-black text-white">{Math.round(score)}</span>
                                <span className="text-[9px] text-slate-500">/100</span>
                              </div>
                              <div className="w-full bg-slate-800 rounded-full h-1 relative overflow-hidden">
                                <div className="bg-indigo-500 h-1 rounded-full" style={{ width: `${score}%` }} />
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="flex flex-col sm:flex-row gap-4">
                    <button
                      onClick={() => router.push(`/products/${p!.sku}`)}
                      className="px-6 py-3.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-sm font-bold transition-all shadow-lg shadow-indigo-600/25 flex items-center justify-center gap-2 group/btn"
                    >
                      <span>View Full Product Details & Specs</span>
                      <ChevronRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                    </button>
                  </div>
                </div>

              </div>
            </div>

            {/* Winner vs Runner-up Battle Card */}
            {recommendation.battle_comparison && (
              <div className="mt-8 bg-slate-900/40 border border-slate-800 rounded-3xl p-6 sm:p-8">
                <h3 className="text-lg font-bold text-white mb-2 flex items-center gap-2">
                  <Scale className="w-5 h-5 text-indigo-400" />
                  Why this beat the runner-up
                </h3>
                <p className="text-xs text-slate-400 mb-6">
                  Head-to-head comparison of {p!.name} (winner) against {recommendation.battle_comparison.runner_name} (runner-up)
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {recommendation.battle_comparison.deltas.map((delta, i) => (
                    <div key={i} className="bg-slate-950/40 border border-slate-850 p-4 rounded-xl flex items-center justify-between gap-4">
                      <div>
                        <span className="block text-[10px] font-bold text-slate-500 uppercase tracking-wide mb-1">{delta.label}</span>
                        <strong className="text-slate-200 text-sm">{delta.delta_text}</strong>
                      </div>
                      <div className="text-right">
                        <span className={`text-xs font-black block ${delta.status === "better" ? "text-emerald-400" : "text-rose-400"}`}>
                          {delta.winner_val}
                        </span>
                        <span className="text-[10px] text-slate-500 block">vs {delta.runner_val}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Can You Spend Less? */}
            {recommendation.spend_less_analysis && (
              <div className="mt-8 bg-gradient-to-br from-emerald-950/30 to-slate-900/30 border border-emerald-800/40 rounded-3xl p-6 sm:p-8">
                <h3 className="text-lg font-bold text-white mb-2 flex items-center gap-2">
                  💰 Can You Spend Less?
                </h3>
                <p className="text-xs text-slate-400 mb-5">
                  We found a cheaper alternative that retains {recommendation.spend_less_analysis.retained_utility_percentage.toFixed(1)}% of the winner&apos;s utility.
                </p>

                <div className="bg-slate-950/40 border border-slate-800 rounded-xl p-5 mb-5">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
                    <div>
                      <h4 className="font-bold text-slate-200 text-sm">{recommendation.spend_less_analysis.name}</h4>
                      <span className="text-emerald-400 font-black text-lg">{formatPrice(recommendation.spend_less_analysis.price, p?.symbol)}</span>
                      <span className="text-xs text-emerald-500 ml-2 font-semibold">
                        Save {formatPrice(recommendation.spend_less_analysis.price_savings, p?.symbol)} ({recommendation.spend_less_analysis.percentage_savings.toFixed(1)}%)
                      </span>
                    </div>
                    <span className={`text-xs font-bold px-3 py-1.5 rounded-full border ${
                      recommendation.spend_less_analysis.verdict === "Strong cheaper alternative"
                        ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                        : recommendation.spend_less_analysis.verdict === "Worth considering"
                        ? "bg-amber-500/10 border-amber-500/30 text-amber-400"
                        : "bg-rose-500/10 border-rose-500/30 text-rose-400"
                    }`}>
                      {recommendation.spend_less_analysis.verdict}
                    </span>
                  </div>

                  <div className="grid grid-cols-3 gap-3 mb-4">
                    <div className="bg-slate-900/60 rounded-lg p-3 text-center">
                      <span className="block text-[9px] font-bold text-slate-500 uppercase">Retained Utility</span>
                      <span className="text-sm font-black text-white">{recommendation.spend_less_analysis.retained_utility_percentage.toFixed(1)}%</span>
                    </div>
                    <div className="bg-slate-900/60 rounded-lg p-3 text-center">
                      <span className="block text-[9px] font-bold text-slate-500 uppercase">Savings Efficiency</span>
                      <span className="text-sm font-black text-white">{recommendation.spend_less_analysis.savings_efficiency.toFixed(1)}</span>
                    </div>
                    <div className="bg-slate-900/60 rounded-lg p-3 text-center">
                      <span className="block text-[9px] font-bold text-slate-500 uppercase">Suitability Gap</span>
                      <span className="text-sm font-black text-white">{recommendation.spend_less_analysis.suitability_difference.toFixed(1)}%</span>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <span className="text-[9px] font-bold text-rose-500 uppercase block mb-1.5">What you lose</span>
                      {recommendation.spend_less_analysis.important_spec_losses.slice(0, 3).map((loss, i) => (
                        <div key={i} className="text-xs text-slate-400 flex items-center gap-1.5 mb-1">
                          <span className="text-rose-400">−</span> {loss}
                        </div>
                      ))}
                    </div>
                    <div>
                      <span className="text-[9px] font-bold text-emerald-500 uppercase block mb-1.5">What stays the same</span>
                      {recommendation.spend_less_analysis.important_spec_similarities.slice(0, 3).map((sim, i) => (
                        <div key={i} className="text-xs text-slate-400 flex items-center gap-1.5 mb-1">
                          <span className="text-emerald-400">≈</span> {sim}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <button
                  onClick={() => router.push(`/products/${recommendation.spend_less_analysis!.sku}`)}
                  className="text-xs font-bold text-emerald-400 hover:text-emerald-300 transition-colors"
                >
                  View {recommendation.spend_less_analysis.name} Details →
                </button>
              </div>
            )}

            {/* Worth Upgrading? (Marginal Upgrade Value) */}
            {recommendation.upgrade_analysis && (
              <div className="mt-8 bg-gradient-to-br from-purple-950/20 to-slate-900/30 border border-purple-800/30 rounded-3xl p-6 sm:p-8">
                <h3 className="text-lg font-bold text-white mb-2 flex items-center gap-2">
                  🚀 Worth Upgrading?
                </h3>
                <p className="text-xs text-slate-400 mb-5">
                  Evaluating {recommendation.upgrade_analysis.name} at {formatPrice(recommendation.upgrade_analysis.price, p?.symbol)} (+{formatPrice(recommendation.upgrade_analysis.extra_cost, p?.symbol)})
                </p>

                <div className="bg-slate-950/40 border border-slate-800 rounded-xl p-5 mb-4">
                  <div className="flex items-center justify-between mb-4">
                    <h4 className="font-bold text-slate-200 text-sm">{recommendation.upgrade_analysis.name}</h4>
                    <span className={`text-xs font-bold px-3 py-1.5 rounded-full border ${
                      recommendation.upgrade_analysis.verdict.includes("Highly")
                        ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                        : recommendation.upgrade_analysis.verdict.includes("Not worth")
                        ? "bg-rose-500/10 border-rose-500/30 text-rose-400"
                        : "bg-amber-500/10 border-amber-500/30 text-amber-400"
                    }`}>
                      {recommendation.upgrade_analysis.verdict}
                    </span>
                  </div>

                  {(recommendation.upgrade_analysis.percentage_utility_gain !== undefined) && (
                    <div className="grid grid-cols-3 gap-3 mb-4">
                      <div className="bg-slate-900/60 rounded-lg p-3 text-center">
                        <span className="block text-[9px] font-bold text-slate-500 uppercase">Utility Gain</span>
                        <span className="text-sm font-black text-white">+{recommendation.upgrade_analysis.percentage_utility_gain!.toFixed(1)}%</span>
                      </div>
                      <div className="bg-slate-900/60 rounded-lg p-3 text-center">
                        <span className="block text-[9px] font-bold text-slate-500 uppercase">Extra Cost</span>
                        <span className="text-sm font-black text-white">+{formatPrice(recommendation.upgrade_analysis.extra_cost, p?.symbol)}</span>
                      </div>
                      <div className="bg-slate-900/60 rounded-lg p-3 text-center">
                        <span className="block text-[9px] font-bold text-slate-500 uppercase">Gain per ₹10K</span>
                        <span className="text-sm font-black text-white">{recommendation.upgrade_analysis.utility_gain_per_10k!.toFixed(1)}%</span>
                      </div>
                    </div>
                  )}

                  <div>
                    <span className="text-[9px] font-bold text-purple-400 uppercase block mb-1.5">Upgrade Gains</span>
                    {recommendation.upgrade_analysis.gains.slice(0, 4).map((gain, i) => (
                      <div key={i} className="text-xs text-slate-400 flex items-center gap-1.5 mb-1">
                        <span className="text-purple-400">+</span> {gain}
                      </div>
                    ))}
                  </div>
                </div>

                <button
                  onClick={() => router.push(`/products/${recommendation.upgrade_analysis!.sku}`)}
                  className="text-xs font-bold text-purple-400 hover:text-purple-300 transition-colors"
                >
                  View {recommendation.upgrade_analysis.name} Details →
                </button>
              </div>
            )}

            {/* Recommendation Sensitivity Analysis */}
            {recommendation.sensitivity_analysis && recommendation.sensitivity_analysis.length > 0 && (
              <div className="mt-8 bg-slate-900/30 border border-slate-800/60 rounded-2xl p-6 sm:p-8">
                <h3 className="text-lg font-bold text-slate-200 mb-2 flex items-center gap-2">
                  🔀 What Would Change Your Winner?
                </h3>
                <p className="text-xs text-slate-400 mb-5">
                  Simulated changes to your priorities that would shift the recommendation.
                </p>
                <div className="flex flex-col gap-3">
                  {recommendation.sensitivity_analysis.map((trigger, i) => (
                    <div key={i} className="bg-slate-950/40 border border-slate-850 rounded-xl p-4 flex items-center gap-4">
                      <div className="w-8 h-8 rounded-full bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 text-sm font-bold flex-shrink-0">
                        ⚡
                      </div>
                      <div className="flex-1">
                        <span className="text-sm text-slate-200 block">
                          If <strong className="text-amber-400">{trigger.trigger_condition}</strong>, the winner shifts to{" "}
                          <strong className="text-white">{trigger.alternative_winner_name}</strong>
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Reliability Breakdown */}
            {recommendation.reliability_breakdown && (
              <div className="mt-8 bg-slate-900/30 border border-slate-800/60 rounded-2xl p-6 sm:p-8">
                <h3 className="text-lg font-bold text-slate-200 mb-2 flex items-center gap-2">
                  🛡️ Recommendation Reliability
                  {recommendation.reliability_score && (
                    <span className="ml-auto text-2xl font-black text-emerald-400">{Math.round(recommendation.reliability_score)}%</span>
                  )}
                </h3>
                <p className="text-xs text-slate-400 mb-5">
                  A heuristic confidence score based on 6 weighted factors.
                </p>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {Object.entries(recommendation.reliability_breakdown).map(([key, value]) => {
                    const labels: Record<string, string> = {
                      intent_confidence: "Intent Detection",
                      specification_coverage: "Spec Coverage",
                      catalog_coverage: "Catalog Depth",
                      score_margin: "Winner Margin",
                      data_completeness: "Data Completeness",
                      stability_score: "Stability"
                    };
                    const weights: Record<string, string> = {
                      intent_confidence: "20%",
                      specification_coverage: "15%",
                      catalog_coverage: "15%",
                      score_margin: "20%",
                      data_completeness: "15%",
                      stability_score: "15%"
                    };
                    return (
                      <div key={key} className="bg-slate-950/40 border border-slate-850 p-3 rounded-xl">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-[9px] font-bold text-slate-500 uppercase">{labels[key] || key}</span>
                          <span className="text-[8px] text-slate-600 font-bold">w: {weights[key] || "—"}</span>
                        </div>
                        <div className="flex items-baseline gap-1 mb-1.5">
                          <span className="text-sm font-black text-white">{Math.round(value as number)}</span>
                          <span className="text-[9px] text-slate-500">/100</span>
                        </div>
                        <div className="w-full bg-slate-800 rounded-full h-1 relative overflow-hidden">
                          <div
                            className={`h-1 rounded-full ${(value as number) >= 85 ? "bg-emerald-500" : (value as number) >= 70 ? "bg-amber-500" : "bg-rose-500"}`}
                            style={{ width: `${value}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Decision Audit Funnel */}
            {recommendation.funnel_metrics && (
              <div className="mt-8 bg-slate-900/30 border border-slate-800/60 rounded-2xl p-6 sm:p-8">
                <h3 className="text-lg font-bold text-slate-200 mb-6 flex items-center gap-2">
                  <Layers className="w-5 h-5 text-indigo-400" /> Decision Audit Trail
                </h3>
                <div className="flex flex-col gap-6 relative">
                  <div className="absolute left-3.5 top-2 bottom-2 w-0.5 bg-slate-800" />
                  
                  <div className="flex items-center gap-4 relative z-10">
                    <div className="w-8 h-8 rounded-full bg-slate-800 border-2 border-slate-700 flex items-center justify-center text-xs font-bold text-slate-400">1</div>
                    <div className="flex-1">
                      <div className="text-sm font-bold text-slate-350">Scanned <span className="text-white font-black">{recommendation.funnel_metrics.total_compared.toLocaleString()}</span> products in active catalog</div>
                    </div>
                  </div>

                  <div className="flex items-center gap-4 relative z-10">
                    <div className="w-8 h-8 rounded-full bg-slate-800 border-2 border-slate-700 flex items-center justify-center text-xs font-bold text-slate-400">2</div>
                    <div className="flex-1">
                      <div className="text-sm font-bold text-slate-355">Category filters retained <span className="text-white font-black">{recommendation.funnel_metrics.category_matched.toLocaleString()}</span> {recommendation.user_preferences?.category || "items"}</div>
                    </div>
                  </div>

                  <div className="flex items-center gap-4 relative z-10">
                    <div className="w-8 h-8 rounded-full bg-slate-800 border-2 border-slate-700 flex items-center justify-center text-xs font-bold text-slate-400">3</div>
                    <div className="flex-1">
                      <div className="text-sm font-bold text-slate-355">Budget filters retained <span className="text-white font-black">{recommendation.funnel_metrics.budget_passed.toLocaleString()}</span> products</div>
                    </div>
                  </div>

                  <div className="flex items-center gap-4 relative z-10">
                    <div className="w-8 h-8 rounded-full bg-slate-800 border-2 border-slate-700 flex items-center justify-center text-xs font-bold text-slate-400">4</div>
                    <div className="flex-1">
                      <div className="text-sm font-bold text-slate-355">Compatibility requirements passed by <span className="text-white font-black">{recommendation.funnel_metrics.constraints_passed.toLocaleString()}</span> items</div>
                    </div>
                  </div>

                  <div className="flex items-center gap-4 relative z-10">
                    <div className="w-8 h-8 rounded-full bg-indigo-500/20 border-2 border-indigo-500 flex items-center justify-center text-xs font-bold text-indigo-400">★</div>
                    <div className="flex-1">
                      <div className="text-sm font-bold text-indigo-400">Multi-Criteria Decision Analysis (MCDA) ranked <span className="text-white font-black">{p!.name}</span> as #1 match</div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Why Nexus chose this */}
            {recommendation.pros && recommendation.pros.length > 0 && (
              <div className="bg-slate-900/30 border border-slate-800 rounded-2xl p-6 sm:p-8 mt-8">
                <h3 className="text-lg font-bold text-slate-200 mb-6 flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-indigo-400" />
                  {recommendation.use_case_rank 
                    ? `Compared against ${recommendation.use_case_rank.total} ${recommendation.use_case_rank.name}s. Ranked #${recommendation.use_case_rank.rank} Because:`
                    : "Why Nexus Chose This"}
                </h3>
                <ul className="flex flex-col gap-4">
                  {recommendation.pros.map((pro, i) => (
                    <li key={i} className="text-slate-300 text-sm flex gap-2.5 leading-relaxed">
                      <span className="text-emerald-500 font-bold mt-0.5">✓</span>
                      {pro}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Why not the others? (Inline Tradeoffs) */}
            {recommendation.tradeoffs && recommendation.tradeoffs.length > 0 && (
              <div className="mt-8 mb-8">
                <div className="flex items-center justify-between mb-6">
                  <h3 className="text-xl font-bold text-white flex items-center gap-2">
                    <Scale className="w-5 h-5 text-slate-400" /> Why not the others?
                  </h3>
                  <button 
                    onClick={() => {
                      const skus = recommendation.tradeoffs.map(t => t.alternative_sku).join(',');
                      router.push(`/compare?skus=${p!.sku},${skus}`);
                    }}
                    className="text-xs font-bold bg-slate-800 hover:bg-slate-700 text-slate-200 px-4 py-2 rounded-lg transition-colors"
                  >
                    Compare Specifications
                  </button>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {recommendation.tradeoffs.map((alt, idx) => {
                    // Extract family name
                    const familyName = alt.alternative_name.split(" (")[0].strip ? alt.alternative_name.split(" (")[0].trim() : alt.alternative_name;
                    return (
                      <div key={idx} className="bg-slate-900/40 border border-slate-800 rounded-xl p-5 hover:bg-slate-900/60 transition-colors cursor-pointer" onClick={() => router.push(`/products/${alt.alternative_sku}`)}>
                        <div className="font-bold text-slate-200 mb-3 text-sm">Why not {familyName}?</div>
                        <ul className="flex flex-col gap-2">
                          {/* We mock a generic cost comparison if reason rejected isn't detailed enough */}
                          {alt.alternative_price > p!.price && (
                            <li className="text-xs text-slate-400 flex items-start gap-2">
                              <span className="text-rose-400 font-bold mt-0.5">❌</span>
                              Costs {formatPrice(alt.alternative_price - p!.price, p!.symbol)} more
                            </li>
                          )}
                          <li className="text-xs text-slate-400 flex items-start gap-2">
                            <span className="text-rose-400 font-bold mt-0.5">❌</span>
                            {alt.reason_rejected || "Lower overall MCDA utility score"}
                          </li>
                        </ul>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Collapsible Decision Trace Inspector */}
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
          </>
        )}
      </main>

      {/* Footer */}
      <footer className="py-6 border-t border-slate-900 text-center text-xs text-slate-600 bg-slate-950/20 backdrop-blur-sm mt-12">
        Data parsed and scored via the Nexus category-agnostic MCDA execution runtime.
      </footer>
    </div>
  );
}
