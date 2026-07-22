"use client";

import React, { useState, useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { env } from "@/config/env";
import { ArrowLeft, Scale, CheckCircle2 } from "lucide-react";

export default function ComparePage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const skusParam = searchParams.get("skus");

  const [products, setProducts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    document.documentElement.classList.add("dark");
    if (skusParam) {
      fetchProducts(skusParam.split(","));
    } else {
      setLoading(false);
    }
  }, [skusParam]);

  const fetchProducts = async (skus: string[]) => {
    try {
      setLoading(true);
      // Fetch all products in parallel
      const responses = await Promise.all(
        skus.map(sku => fetch(`${env.NEXT_PUBLIC_API_URL}/api/products/${sku.trim()}`))
      );
      
      const data = await Promise.all(
        responses.filter(r => r.ok).map(r => r.json())
      );
      setProducts(data);
    } catch (err) {
      console.error("Failed to fetch comparison products", err);
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
        <p className="text-slate-400 text-sm animate-pulse">Loading comparison data...</p>
      </div>
    );
  }

  if (!products.length) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center flex-col gap-4">
        <p className="text-slate-400">No products selected for comparison.</p>
        <button onClick={() => router.back()} className="text-indigo-400 hover:underline">Go Back</button>
      </div>
    );
  }

  // Extract all unique spec keys to build the table
  const allSpecKeys = new Set<string>();
  products.forEach(p => {
    Object.keys(p.specs || {}).forEach(k => {
      // Ignore complex structures for the table
      if (typeof p.specs[k] !== 'object' && k !== 'image_url') {
        allSpecKeys.add(k);
      }
    });
  });

  const specKeysArray = Array.from(allSpecKeys).sort();

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 relative overflow-x-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(99,102,241,0.05),transparent_70%)] pointer-events-none" />

      <header className="sticky top-0 z-40 w-full border-b border-slate-900 bg-slate-950/80 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <button
            onClick={() => router.back()}
            className="flex items-center gap-2 text-sm font-medium text-slate-400 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-4 h-4" /> Back
          </button>
          <div className="flex items-center gap-2">
            <Scale className="w-4 h-4 text-indigo-400" />
            <span className="text-sm font-bold text-white tracking-wide">Product Comparison</span>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-12 w-full relative z-10">
        <h1 className="text-3xl md:text-5xl font-black text-white tracking-tight mb-4 text-center">
          Compare Specifications
        </h1>
        <p className="text-slate-400 text-center mb-12 max-w-2xl mx-auto">
          Detailed side-by-side analysis of your selected products to help you make the best decision.
        </p>

        <div className="bg-slate-900/40 border border-slate-800 rounded-2xl overflow-hidden backdrop-blur-sm shadow-2xl">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[800px] border-collapse text-left">
              <thead>
                <tr>
                  <th className="p-6 border-b border-r border-slate-800 bg-slate-900/60 w-[200px]">
                    <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Features</span>
                  </th>
                  {products.map((p, i) => (
                    <th key={p.sku} className={`p-6 border-b ${i < products.length - 1 ? 'border-r' : ''} border-slate-800 bg-slate-900/60 w-[250px] text-center align-top relative`}>
                      {i === 0 && (
                        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-amber-500 to-yellow-400" />
                      )}
                      <div className="w-24 h-24 mx-auto mb-3 flex items-center justify-center p-2 bg-slate-950/60 rounded-xl border border-slate-800">
                        <img
                          src={p.specs?.image_url && typeof p.specs.image_url === "string" && p.specs.image_url.startsWith("http") ? p.specs.image_url : "/images/image-unavailable.svg"}
                          alt={p.name}
                          onError={(e) => { (e.currentTarget as HTMLImageElement).src = "/images/image-unavailable.svg"; }}
                          className="w-full h-full object-contain"
                        />
                      </div>
                      <div className="text-sm font-black text-white mb-2">{p.name}</div>
                      <div className="text-xl font-bold text-indigo-400 mb-4">{formatPrice(p.price_inr)}</div>
                      <button 
                        onClick={() => router.push(`/products/${p.sku}`)}
                        className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-lg w-full transition-colors"
                      >
                        View Full Details
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {specKeysArray.map((key) => {
                  // Format the key to be more readable
                  const formattedKey = key.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
                  
                  return (
                    <tr key={key} className="hover:bg-slate-800/30 transition-colors">
                      <td className="p-4 border-b border-r border-slate-800/60 text-sm font-semibold text-slate-400 bg-slate-900/20">
                        {formattedKey}
                      </td>
                      {products.map((p, i) => (
                        <td key={p.sku} className={`p-4 border-b ${i < products.length - 1 ? 'border-r' : ''} border-slate-800/60 text-sm text-slate-300 text-center`}>
                          {p.specs[key] !== undefined && p.specs[key] !== null && p.specs[key] !== "" 
                            ? (typeof p.specs[key] === 'boolean' 
                                ? (p.specs[key] ? <CheckCircle2 className="w-4 h-4 text-emerald-400 mx-auto" /> : <span className="text-slate-600">—</span>) 
                                : String(p.specs[key])) 
                            : <span className="text-slate-600">—</span>}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  );
}
