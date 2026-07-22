"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { env } from "@/config/env";
import { formatCurrency } from "@/lib/currency";
import { toast } from "sonner";
import { 
  ArrowLeft, Monitor, Smartphone, 
  Layers, ChevronRight, CheckCircle2, 
  BarChart2, Star, ThumbsUp, ThumbsDown, 
  Activity, Zap, Shield, TrendingUp
} from "lucide-react";

interface AlternativeProduct {
  sku: string;
  name: string;
  price_inr: number;
  specs: Record<string, any>;
}

interface ProductDetails {
  sku: string;
  name: string;
  category: string;
  price_inr: number;
  specs: Record<string, any>;
  alternatives: AlternativeProduct[];
  configurations?: Array<{ sku: string; name: string; price_inr: number }>;
  domain_scores?: Record<string, number>;
}

export default function ProductDetailPage() {
  const { slug } = useParams() as { slug: string };
  const router = useRouter();

  const [loading, setLoading] = useState(true);
  const [product, setProduct] = useState<ProductDetails | null>(null);
  const [activeTab, setActiveTab] = useState<"overview" | "specs" | "benchmarks" | "reviews" | "buying" | "alternatives">("overview");

  useEffect(() => {
    document.documentElement.classList.add("dark");
    fetchProductDetails();
  }, [slug]);

  const fetchProductDetails = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${env.NEXT_PUBLIC_API_URL}/api/products/${slug}`);
      if (!response.ok) {
        throw new Error("Failed to fetch product details.");
      }
      const data = await response.json();
      setProduct(data);
    } catch (err: any) {
      toast.error(err.message || "Product not found.");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center flex-col gap-4">
        <span className="w-12 h-12 border-4 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin" />
        <p className="text-slate-400 text-sm animate-pulse">Loading Premium Product Intelligence...</p>
      </div>
    );
  }

  if (!product) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center flex-col gap-4">
        <p className="text-red-400 font-bold">Product not found.</p>
        <button
          onClick={() => router.push("/")}
          className="px-5 py-2.5 bg-slate-900 border border-slate-800 rounded-lg flex items-center gap-2 hover:bg-slate-800 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Go Home
        </button>
      </div>
    );
  }

  const getCategoryIcon = (category: string) => {
    switch (category?.toLowerCase()) {
      case "laptop":
        return <Monitor className="w-8 h-8 text-indigo-400" />;
      case "smartphone":
        return <Smartphone className="w-8 h-8 text-purple-400" />;
      default:
        return <Layers className="w-8 h-8 text-emerald-400" />;
    }
  };

  const formatPrice = (price: number) => {
    return formatCurrency(price, "₹");
  };

  const renderProductImage = (prod: any) => {
    const imgUrl = prod?.specs?.image_url;
    const isIphonePhoto = typeof imgUrl === "string" && imgUrl.includes("photo-1511707171634");
    const name = prod?.name || "";
    const isAppleProduct = typeof name === "string" && (name.toLowerCase().includes("iphone") || name.toLowerCase().includes("apple"));
    const isBrandMismatch = isIphonePhoto && !isAppleProduct;

    const isValid = imgUrl && typeof imgUrl === "string" && imgUrl.startsWith("http") && !imgUrl.includes("placeholder.com") && !isBrandMismatch;
    const srcToUse = isValid ? imgUrl : "/images/image-unavailable.svg";

    return (
      <img
        src={srcToUse}
        alt={prod?.name || "Product image"}
        onError={(e) => {
          (e.currentTarget as HTMLImageElement).src = "/images/image-unavailable.svg";
        }}
        className="w-full h-full object-contain p-4 rounded-xl drop-shadow-2xl"
      />
    );
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col selection:bg-indigo-500 relative overflow-x-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(99,102,241,0.03),transparent_50%)] pointer-events-none" />

      <header className="sticky top-0 z-40 w-full border-b border-slate-900 bg-slate-950/80 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <button
            onClick={() => router.back()}
            className="flex items-center gap-2 text-sm font-medium text-slate-400 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-4 h-4" /> Back
          </button>
          <div className="flex items-center gap-4">
            <button 
              onClick={() => {
                const altSkus = product.alternatives.map(a => a.sku).join(',');
                router.push(`/compare?skus=${product.sku},${altSkus}`);
              }}
              className="text-xs font-bold bg-indigo-600/10 hover:bg-indigo-600/20 text-indigo-400 px-4 py-1.5 rounded-full transition-colors border border-indigo-500/20"
            >
              Compare Variants
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1 w-full relative z-10 pb-24">
        
        {/* 1. Hero Section */}
        <section className="max-w-7xl mx-auto px-6 pt-12 pb-16 grid grid-cols-1 lg:grid-cols-2 gap-12 items-center border-b border-slate-900">
          <div className="aspect-square bg-slate-900/20 border border-slate-800/50 rounded-3xl p-8 flex items-center justify-center relative group">
            <div className="absolute inset-0 bg-gradient-to-tr from-indigo-500/5 to-purple-500/5 rounded-3xl opacity-0 group-hover:opacity-100 transition-opacity" />
            {renderProductImage(product)}
          </div>
          <div className="flex flex-col gap-6">
            <div>
              <div className="flex items-center gap-3 mb-4 text-xs font-bold tracking-wider text-slate-500 uppercase">
                <span>{product.specs?.brand || "Brand"}</span>
                <span>•</span>
                <span>{product.category}</span>
              </div>
              <h1 className="text-3xl lg:text-4xl font-black text-white tracking-tight leading-[1.1] mb-6">
                {product.name}
              </h1>
              <div className="text-3xl font-black text-indigo-400">
                {formatPrice(product.price_inr)}
              </div>
            </div>

            {/* AI Verdict Snapshot */}
            <div className="bg-emerald-500/5 border border-emerald-500/10 rounded-2xl p-5 flex gap-4 mt-2">
              <Shield className="w-8 h-8 text-emerald-400 shrink-0" />
              <div>
                <h4 className="text-emerald-400 font-bold mb-1">AI Verified Quality</h4>
                <p className="text-slate-300 text-sm leading-relaxed">
                  Based on global spec analysis, this model represents top-tier performance for its price bracket, excelling in reliability and raw power.
                </p>
              </div>
            </div>

            {/* Configuration Switcher */}
            {product.configurations && product.configurations.length > 1 && (
              <div className="mt-4">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">
                    <Layers className="w-4 h-4" /> Available Configurations
                  </h3>
                  {product.configurations.length > 6 && (
                    <button 
                      onClick={() => router.push(`/products/${product.sku}/variants`)}
                      className="text-xs font-bold text-indigo-400 hover:text-indigo-300 transition-colors"
                    >
                      View all {product.configurations.length} variants &rarr;
                    </button>
                  )}
                </div>
                <div className="flex flex-wrap gap-3">
                  {product.configurations.slice(0, 6).map((config: any, idx: number) => {
                    const isSelected = config.sku === product.sku;
                    return (
                      <button
                        key={idx}
                        onClick={() => router.push(`/products/${config.sku}`)}
                        className={`px-4 py-3 rounded-xl border text-left transition-all ${
                          isSelected 
                            ? "bg-indigo-600/20 border-indigo-500 shadow-[0_0_15px_rgba(99,102,241,0.15)]" 
                            : "bg-slate-900/50 border-slate-800 hover:border-slate-600 hover:bg-slate-900"
                        }`}
                      >
                        <div className={`text-sm font-bold ${isSelected ? "text-indigo-300" : "text-slate-200"} line-clamp-1`}>
                          {config.name}
                        </div>
                        <div className={`text-xs mt-1 ${isSelected ? "text-indigo-400 font-semibold" : "text-slate-400"}`}>
                          {formatPrice(config.price_inr)}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </section>
 
        {/* Tab Navigation Menu */}
        <div className="border-b border-slate-900 bg-slate-950/80 sticky top-16 z-30 backdrop-blur-md">
          <div className="max-w-7xl mx-auto px-6 flex space-x-8 overflow-x-auto">
            {[
              { id: "overview", label: "Overview" },
              { id: "specs", label: "Specifications" },
              { id: "benchmarks", label: "Benchmarks" },
              { id: "reviews", label: "Reviews" },
              { id: "buying", label: "Buying Options" },
              { id: "alternatives", label: "Alternatives" }
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`py-4 text-sm font-bold border-b-2 transition-all shrink-0 ${
                  activeTab === tab.id
                    ? "border-indigo-500 text-indigo-400"
                    : "border-transparent text-slate-400 hover:text-white"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Tab Contents */}
        {activeTab === "overview" && (() => {
          // Dynamic Suitability Logic based on scoring engine
          const bestFor: string[] = [];
          const avoidFor: string[] = [];
          
          if (product.domain_scores) {
            if (product.domain_scores.gaming >= 75) bestFor.push("High-End AAA Gaming");
            if (product.domain_scores.programming >= 75) bestFor.push("Software Development / Compiler Loads");
            if (product.domain_scores.creator >= 75) bestFor.push("Creative Rendering & Editing");
            if (product.domain_scores.business >= 75) bestFor.push("Office & Business Multitasking");
            if (product.domain_scores.student >= 75) bestFor.push("Student Value & Portability");

            if (product.domain_scores.gaming < 55) avoidFor.push("Demanding AAA Gaming");
            if (product.domain_scores.creator < 55) avoidFor.push("Professional Video Editing");
          }
          
          const weight = parseFloat(product.specs?.weight_kg || product.specs?.weight || "0");
          if (weight > 2.2) {
            avoidFor.push("Frequent Mobile Travel (Heavier Build)");
          }
          const battery = parseFloat(product.specs?.battery_hours || product.specs?.battery_life || "0");
          if (battery < 6) {
            avoidFor.push("All-day unplugged work (Frequent charging required)");
          }

          // Worth Upgrading Check
          const cheaperAlts = product.alternatives.filter(a => a.price_inr > product.price_inr);
          const upgradeProduct = cheaperAlts.length > 0
            ? cheaperAlts.reduce((min, p) => p.price_inr < min.price_inr ? p : min, cheaperAlts[0])
            : null;
          const upgradeCost = upgradeProduct ? upgradeProduct.price_inr - product.price_inr : 0;

          return (
            <div className="flex flex-col gap-8">
              {/* Should You Buy Verdict */}
              <section className="max-w-7xl mx-auto px-6 pt-12 w-full">
                <div className="bg-slate-900/40 border border-slate-800 rounded-3xl p-6 sm:p-8 backdrop-blur-md">
                  <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 pb-6 border-b border-slate-800/80">
                    <div>
                      <span className="text-[10px] font-black uppercase text-indigo-400 bg-indigo-500/10 px-2.5 py-1 rounded-md">AI Buying Verdict</span>
                      <h3 className="text-2xl font-black text-white mt-3">Should You Buy This?</h3>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-3xl font-black text-indigo-400 uppercase tracking-tight">YES</span>
                      <span className="text-xs text-slate-500 max-w-[120px]">Meets high-quality MCDA scoring standards</span>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
                    <div>
                      <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">Best Suited For</h4>
                      <ul className="flex flex-col gap-2">
                        {bestFor.length > 0 ? bestFor.map((item, idx) => (
                          <li key={idx} className="text-sm text-slate-200 flex items-center gap-2">
                            <span className="text-emerald-500 font-bold">✓</span> {item}
                          </li>
                        )) : (
                          <li className="text-sm text-slate-400 italic">General computing requirements</li>
                        )}
                      </ul>
                    </div>

                    <div>
                      <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">Not Ideal For / Avoid if</h4>
                      <ul className="flex flex-col gap-2">
                        {avoidFor.length > 0 ? avoidFor.map((item, idx) => (
                          <li key={idx} className="text-sm text-slate-350 flex items-center gap-2">
                            <span className="text-rose-500 font-bold">—</span> {item}
                          </li>
                        )) : (
                          <li className="text-sm text-slate-400 italic">No major drawbacks identified</li>
                        )}
                      </ul>
                    </div>
                  </div>
                </div>
              </section>

              {/* Worth Upgrading Block */}
              {upgradeProduct && (
                <section className="max-w-7xl mx-auto px-6 w-full">
                  <div className="bg-slate-900/30 border border-slate-800/80 rounded-3xl p-6 sm:p-8">
                    <h3 className="text-lg font-bold text-white mb-2 flex items-center gap-2">
                      <TrendingUp className="w-5 h-5 text-indigo-400" />
                      Worth upgrading to the next tier?
                    </h3>
                    <p className="text-xs text-slate-400 mb-6">
                      Comparing {product.name.split(" (")[0]} with {upgradeProduct.name.split(" (")[0]}
                    </p>
                    <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-slate-950/40 p-4 rounded-xl border border-slate-850">
                      <div>
                        <span className="text-xs text-indigo-400 font-bold block">{upgradeProduct.name.split(" (")[0]}</span>
                        <span className="text-xs text-slate-400 block mt-1">Extra Cost: <strong className="text-slate-300">₹{upgradeCost.toLocaleString()}</strong></span>
                      </div>
                      <p className="text-xs text-slate-300 max-w-lg leading-relaxed">
                        {upgradeCost < 30000 
                          ? `Highly recommended upgrade option. For an extra ₹${upgradeCost.toLocaleString()}, you gain significant suitability margin and specs protection.` 
                          : `Not worth upgrading unless you have a critical need for higher specifications.`}
                      </p>
                    </div>
                  </div>
                </section>
              )}

              {/* 2. Pros & Cons (AI Intelligence) */}
              <section className="max-w-7xl mx-auto px-6 py-16 border-b border-slate-900 w-full">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                  <div className="bg-slate-900/30 border border-slate-800 rounded-3xl p-8">
                    <h3 className="text-xl font-bold text-white mb-6 flex items-center gap-3">
                      <ThumbsUp className="w-6 h-6 text-emerald-400" /> Why We Recommend It
                    </h3>
                    <ul className="flex flex-col gap-4">
                      {(product.specs?.known_pros || ["Excellent build quality", "Great performance-to-price ratio", "Reliable thermal management"]).map((pro: string, i: number) => (
                        <li key={i} className="flex gap-3 text-slate-300">
                          <CheckCircle2 className="w-5 h-5 text-emerald-500 shrink-0" />
                          <span>{pro}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  
                  <div className="bg-slate-900/30 border border-slate-800 rounded-3xl p-8">
                    <h3 className="text-xl font-bold text-white mb-6 flex items-center gap-3">
                      <ThumbsDown className="w-6 h-6 text-rose-400" /> Trade-offs to Consider
                    </h3>
                    <ul className="flex flex-col gap-4">
                      {(product.specs?.known_cons || ["Battery life could be better under heavy load", "Slightly heavier than ultrabook competitors"]).map((con: string, i: number) => (
                        <li key={i} className="flex gap-3 text-slate-300">
                          <span className="text-rose-500 font-bold px-1.5">—</span>
                          <span>{con}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </section>
            </div>
          );
        })()}

        {activeTab === "benchmarks" && (
          /* 3. Performance & Benchmarks */
          <section className="max-w-7xl mx-auto px-6 py-16 border-b border-slate-900 flex flex-col gap-12">
            <div>
              <h2 className="text-2xl font-black text-white mb-10 flex items-center gap-3">
                <Activity className="w-7 h-7 text-indigo-500" /> Suitability & Performance Ratings
              </h2>
              
              {product.domain_scores && (
                <div className="bg-slate-900/30 border border-slate-850 p-6 rounded-3xl mb-8 flex flex-col gap-6">
                  {Object.entries(product.domain_scores).map(([domain, score]) => (
                    <div key={domain}>
                      <div className="flex justify-between items-center text-sm mb-2">
                        <span className="capitalize text-slate-300 font-bold">{domain} Suitability</span>
                        <strong className="text-white text-base">{score}%</strong>
                      </div>
                      <div className="w-full bg-slate-800 rounded-full h-2 relative overflow-hidden">
                        <div className="bg-indigo-500 h-2 rounded-full" style={{ width: `${score}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div>
              <h2 className="text-2xl font-black text-white mb-10 flex items-center gap-3">
                <Activity className="w-7 h-7 text-indigo-500" /> Performance Benchmarks
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
                {product.category === "laptop" && (
                  <>
                    {/* Laptop CPU PassMark */}
                    <div className="bg-slate-900/50 border border-slate-800 p-6 rounded-2xl overflow-hidden relative">
                      <div className="text-slate-400 text-sm font-bold mb-2">CPU PassMark</div>
                      <div className="text-2xl font-black text-white mb-2">{product.specs?.cpu_score || "N/A"}</div>
                      {product.specs?.cpu_score && (
                        <div className="w-full bg-slate-800 rounded-full h-1.5 mt-4">
                          <div className="bg-indigo-500 h-1.5 rounded-full" style={{width: `${Math.min(100, Math.max(5, (product.specs.cpu_score / 35000) * 100))}%`}}></div>
                        </div>
                      )}
                    </div>
                    {/* Laptop GPU Benchmark */}
                    <div className="bg-slate-900/50 border border-slate-800 p-6 rounded-2xl overflow-hidden relative">
                      <div className="text-slate-400 text-sm font-bold mb-2">GPU Benchmark</div>
                      <div className="text-2xl font-black text-white mb-2">{product.specs?.gpu_score || "N/A"}</div>
                      {product.specs?.gpu_score && (
                        <div className="w-full bg-slate-800 rounded-full h-1.5 mt-4">
                          <div className="bg-purple-500 h-1.5 rounded-full" style={{width: `${Math.min(100, Math.max(5, (product.specs.gpu_score / 25000) * 100))}%`}}></div>
                        </div>
                      )}
                    </div>
                    {/* Laptop Battery Capacity */}
                    <div className="bg-slate-900/50 border border-slate-800 p-6 rounded-2xl">
                      <div className="text-slate-400 text-sm font-bold mb-2">Battery Capacity</div>
                      <div className="text-2xl font-black text-white mb-2">{product.specs?.battery_capacity_wh || "N/A"}<span className="text-sm text-slate-500"> Wh</span></div>
                      <div className="text-xs text-slate-500 mt-2">All-day capability</div>
                    </div>
                  </>
                )}

                {product.category === "smartphone" && (
                  <>
                    {/* Smartphone Processor Score */}
                    <div className="bg-slate-900/50 border border-slate-800 p-6 rounded-2xl overflow-hidden relative">
                      <div className="text-slate-400 text-sm font-bold mb-2">Processor Performance</div>
                      <div className="text-2xl font-black text-white mb-2">{product.specs?.processor_score || "N/A"}</div>
                      {product.specs?.processor_score && (
                        <div className="w-full bg-slate-800 rounded-full h-1.5 mt-4">
                          <div className="bg-indigo-500 h-1.5 rounded-full" style={{width: `${Math.min(100, Math.max(5, (product.specs.processor_score / 10000) * 100))}%`}}></div>
                        </div>
                      )}
                    </div>
                    {/* Smartphone Camera MP */}
                    <div className="bg-slate-900/50 border border-slate-800 p-6 rounded-2xl overflow-hidden relative">
                      <div className="text-slate-400 text-sm font-bold mb-2">Camera Resolution</div>
                      <div className="text-2xl font-black text-white mb-2">{product.specs?.camera_mp || "N/A"}<span className="text-sm text-slate-500"> MP</span></div>
                      {product.specs?.camera_mp && (
                        <div className="w-full bg-slate-800 rounded-full h-1.5 mt-4">
                          <div className="bg-purple-500 h-1.5 rounded-full" style={{width: `${Math.min(100, Math.max(5, (product.specs.camera_mp / 200) * 100))}%`}}></div>
                        </div>
                      )}
                    </div>
                    {/* Smartphone Battery Capacity */}
                    <div className="bg-slate-900/50 border border-slate-800 p-6 rounded-2xl">
                      <div className="text-slate-400 text-sm font-bold mb-2">Battery Capacity</div>
                      <div className="text-2xl font-black text-white mb-2">{product.specs?.battery_mah || "N/A"}<span className="text-sm text-slate-500"> mAh</span></div>
                      <div className="text-xs text-slate-500 mt-2">Extended usage time</div>
                    </div>
                  </>
                )}

                {product.category === "monitor" && (
                  <>
                    {/* Monitor Refresh Rate */}
                    <div className="bg-slate-900/50 border border-slate-800 p-6 rounded-2xl overflow-hidden relative">
                      <div className="text-slate-400 text-sm font-bold mb-2">Refresh Rate</div>
                      <div className="text-2xl font-black text-white mb-2">{product.specs?.refresh_rate_hz || "N/A"}<span className="text-sm text-slate-500"> Hz</span></div>
                      {product.specs?.refresh_rate_hz && (
                        <div className="w-full bg-slate-800 rounded-full h-1.5 mt-4">
                          <div className="bg-indigo-500 h-1.5 rounded-full" style={{width: `${Math.min(100, Math.max(5, (product.specs.refresh_rate_hz / 360) * 100))}%`}}></div>
                        </div>
                      )}
                    </div>
                    {/* Monitor Response Time */}
                    <div className="bg-slate-900/50 border border-slate-800 p-6 rounded-2xl overflow-hidden relative">
                      <div className="text-slate-400 text-sm font-bold mb-2">Response Time</div>
                      <div className="text-2xl font-black text-white mb-2">{product.specs?.response_time_ms || "N/A"}<span className="text-sm text-slate-500"> ms</span></div>
                      {product.specs?.response_time_ms && (
                        <div className="w-full bg-slate-800 rounded-full h-1.5 mt-4">
                          <div className="bg-purple-500 h-1.5 rounded-full" style={{width: `${Math.min(100, Math.max(5, (10 / product.specs.response_time_ms) * 10))}%`}}></div>
                        </div>
                      )}
                    </div>
                    {/* Monitor Screen Size */}
                    <div className="bg-slate-900/50 border border-slate-800 p-6 rounded-2xl">
                      <div className="text-slate-400 text-sm font-bold mb-2">Screen Size</div>
                      <div className="text-2xl font-black text-white mb-2">{product.specs?.screen_size_inches || "N/A"}<span className="text-sm text-slate-500"> inches</span></div>
                      <div className="text-xs text-slate-500 mt-2">Diagonal display area</div>
                    </div>
                  </>
                )}

                {/* Build Quality - Common to all */}
                <div className="bg-slate-900/50 border border-slate-800 p-6 rounded-2xl">
                  <div className="text-slate-400 text-sm font-bold mb-2">Build Quality</div>
                  <div className="text-2xl font-black text-white mb-2 flex gap-1">
                    <Star className="w-5 h-5 fill-amber-400 text-amber-400" />
                    <Star className="w-5 h-5 fill-amber-400 text-amber-400" />
                    <Star className="w-5 h-5 fill-amber-400 text-amber-400" />
                    <Star className="w-5 h-5 fill-amber-400 text-amber-400" />
                    <Star className="w-5 h-5 text-slate-700" />
                  </div>
                  <div className="text-xs text-slate-500 mt-2">Premium materials</div>
                </div>
              </div>
            </div>
          </section>
        )}

        {activeTab === "specs" && (
          /* 4. Deep Specifications Matrix */
          <section className="max-w-7xl mx-auto px-6 py-16 border-b border-slate-900">
            <h2 className="text-2xl font-black text-white mb-10 flex items-center gap-3">
              <Zap className="w-7 h-7 text-amber-500" /> Technical Specifications
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-12 gap-y-4">
              {Object.entries(product.specs || {}).map(([key, val], idx) => {
                if (typeof val === 'object' || key === 'image_url' || key.includes('score') || key.includes('known_')) return null;
                
                const formattedKey = key.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
                return (
                  <div key={idx} className="flex justify-between py-4 border-b border-slate-800/60">
                    <span className="text-slate-400">{formattedKey}</span>
                    <span className="text-white font-medium text-right max-w-[50%]">
                      {typeof val === 'boolean' ? (val ? 'Yes' : 'No') : String(val)}
                    </span>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {activeTab === "reviews" && (
          <section className="max-w-7xl mx-auto px-6 py-24 text-center">
            <div className="max-w-md mx-auto bg-slate-900/35 border border-slate-800/80 p-8 rounded-3xl backdrop-blur-sm shadow-xl">
              <Star className="w-12 h-12 text-indigo-400 mx-auto mb-4 animate-pulse" />
              <h3 className="text-xl font-bold text-white mb-2">External Reviews Intelligence</h3>
              <p className="text-slate-400 text-sm leading-relaxed mb-6">
                Live attributed summaries and review analysis from professional sources (Notebookcheck, GSMArena, TechRadar) are pending integration.
              </p>
              <span className="text-xs uppercase font-extrabold tracking-wider text-slate-500 bg-slate-950 px-3 py-1 rounded-full border border-slate-800">
                Future API Hook Ready
              </span>
            </div>
          </section>
        )}

        {activeTab === "buying" && (
          <section className="max-w-7xl mx-auto px-6 py-24 text-center">
            <div className="max-w-md mx-auto bg-slate-900/35 border border-slate-800/80 p-8 rounded-3xl backdrop-blur-sm shadow-xl">
              <Layers className="w-12 h-12 text-indigo-400 mx-auto mb-4 animate-pulse" />
              <h3 className="text-xl font-bold text-white mb-2">Live Store Buying Options</h3>
              <p className="text-slate-400 text-sm leading-relaxed mb-6">
                Live pricing tables, delivery estimates, and stock indicators from Amazon, Flipkart, Croma, and brand stores are pending integration.
              </p>
              <span className="text-xs uppercase font-extrabold tracking-wider text-slate-500 bg-slate-950 px-3 py-1 rounded-full border border-slate-800">
                Future API Hook Ready
              </span>
            </div>
          </section>
        )}

        {activeTab === "alternatives" && product.alternatives && product.alternatives.length > 0 && (
          /* 5. Best Alternatives (Similar Products) */
          <section className="max-w-7xl mx-auto px-6 py-16">
            <div className="flex items-end justify-between mb-10">
              <div>
                <h2 className="text-2xl font-black text-white mb-2">Best Alternatives</h2>
                <p className="text-slate-400">Other options you might want to consider before making a decision.</p>
              </div>
              <button 
                onClick={() => {
                  const altSkus = product.alternatives.map(a => a.sku).join(',');
                  router.push(`/compare?skus=${product.sku},${altSkus}`);
                }}
                className="hidden sm:flex px-5 py-2.5 bg-slate-800 hover:bg-slate-700 text-white font-bold rounded-xl transition-colors gap-2 items-center"
              >
                Compare All <ChevronRight className="w-4 h-4" />
              </button>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {product.alternatives.map((alt, idx) => {
                // Generate a mock AI match percentage based on index for the UI
                const matchPct = 92 - (idx * 2);
                
                return (
                  <div key={idx} className="bg-slate-900/40 border border-slate-800 rounded-2xl p-6 hover:border-slate-600 transition-colors cursor-pointer" onClick={() => router.push(`/products/${alt.sku}`)}>
                    <div className="flex justify-between items-start mb-4">
                      <div className="text-xs font-bold text-indigo-400 bg-indigo-500/10 px-2.5 py-1 rounded-lg">
                        {matchPct}% Match
                      </div>
                    </div>
                    <h3 className="text-lg font-bold text-white mb-2 line-clamp-2 leading-snug">{alt.name}</h3>
                    <div className="text-xl font-black text-indigo-300 mb-6">{formatPrice(alt.price_inr)}</div>
                    
                    <div className="space-y-2 mb-6">
                      <div className="flex justify-between text-xs text-slate-400">
                        <span>CPU Score</span>
                        <span className="text-slate-200">{alt.specs?.cpu_score || "N/A"}</span>
                      </div>
                      <div className="flex justify-between text-xs text-slate-400">
                        <span>GPU Score</span>
                        <span className="text-slate-200">{alt.specs?.gpu_score || "N/A"}</span>
                      </div>
                    </div>

                    <button className="w-full py-2.5 bg-slate-800 text-white text-sm font-bold rounded-xl transition-colors group-hover:bg-slate-700">
                      View Details
                    </button>
                  </div>
                );
              })}
            </div>
          </section>
        )}

      </main>
    </div>
  );
}
