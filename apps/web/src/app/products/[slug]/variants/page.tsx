"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { env } from "@/config/env";
import { toast } from "sonner";
import { ArrowLeft, Layers, Filter } from "lucide-react";

export default function VariantsPage() {
  const { slug } = useParams() as { slug: string };
  const router = useRouter();

  const [loading, setLoading] = useState(true);
  const [product, setProduct] = useState<any>(null);

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

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(price);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center flex-col gap-4">
        <span className="w-12 h-12 border-4 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin" />
        <p className="text-slate-400 text-sm animate-pulse">Loading all available variants...</p>
      </div>
    );
  }

  if (!product || !product.configurations || product.configurations.length === 0) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center flex-col gap-4">
        <p className="text-red-400 font-bold">No variants found for this product.</p>
        <button
          onClick={() => router.back()}
          className="px-5 py-2.5 bg-slate-900 border border-slate-800 rounded-lg flex items-center gap-2 hover:bg-slate-800 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Go Back
        </button>
      </div>
    );
  }

  // Get family name (strip out parenthesis)
  const familyName = product.name.split(" (")[0].trim();

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col relative overflow-x-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(99,102,241,0.03),transparent_50%)] pointer-events-none" />

      <header className="sticky top-0 z-40 w-full border-b border-slate-900 bg-slate-950/80 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <button
            onClick={() => router.back()}
            className="flex items-center gap-2 text-sm font-medium text-slate-400 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-4 h-4" /> Back to {familyName}
          </button>
        </div>
      </header>

      <main className="flex-1 max-w-7xl mx-auto px-6 py-12 w-full relative z-10">
        <div className="mb-10">
          <div className="flex items-center gap-3 mb-2 text-xs font-bold tracking-wider text-slate-500 uppercase">
            <span>{product.specs?.brand || "Brand"}</span>
            <span>•</span>
            <span>{product.category}</span>
          </div>
          <h1 className="text-3xl lg:text-5xl font-black text-white tracking-tight mb-4">
            All Configurations
          </h1>
          <p className="text-slate-400 max-w-2xl text-lg">
            Showing all {product.configurations.length} available variants for the <span className="text-white font-bold">{familyName}</span> family.
          </p>
        </div>

        {/* Configurations Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {product.configurations.map((config: any, idx: number) => {
            const isSelected = config.sku === product.sku;
            return (
              <button
                key={idx}
                onClick={() => router.push(`/products/${config.sku}`)}
                className={`p-5 rounded-2xl border text-left transition-all flex flex-col justify-between h-full group ${
                  isSelected 
                    ? "bg-indigo-600/10 border-indigo-500/50 shadow-[0_0_20px_rgba(99,102,241,0.1)]" 
                    : "bg-slate-900/40 border-slate-800 hover:border-slate-600 hover:bg-slate-900"
                }`}
              >
                <div>
                  {isSelected && (
                    <div className="text-[10px] font-bold text-indigo-400 uppercase tracking-wider mb-2">Currently Viewing</div>
                  )}
                  <h3 className={`text-base font-bold mb-4 leading-snug group-hover:text-white transition-colors ${isSelected ? "text-indigo-200" : "text-slate-300"}`}>
                    {config.name}
                  </h3>
                </div>
                <div>
                  <div className={`text-xl font-black ${isSelected ? "text-indigo-400" : "text-slate-200"}`}>
                    {formatPrice(config.price_inr)}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </main>
    </div>
  );
}
