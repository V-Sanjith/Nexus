'use client';

import { motion, AnimatePresence } from 'framer-motion';
import type { HolographicProduct } from './product-data';

interface RecommendationStackProps {
  products: HolographicProduct[];
  isMobile: boolean;
}

export function RecommendationStack({ products, isMobile }: RecommendationStackProps) {
  // Hide on very small screens
  if (isMobile) return null;

  return (
    <AnimatePresence>
      {products.length > 0 && (
        <motion.div
          initial={{ opacity: 0, x: 40 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: 40 }}
          className="absolute right-3 top-14 flex flex-col gap-1.5 z-[22] pointer-events-auto"
        >
          <div className="text-[7px] font-bold font-mono text-slate-600 tracking-[0.15em] uppercase mb-0.5 px-1">
            AI RANKED
          </div>
          {products.slice(0, 4).map((product, idx) => (
            <motion.div
              key={product.id}
              layoutId={`stack-${product.id}`}
              initial={{ opacity: 0, scale: 0.9, x: 20 }}
              animate={{
                opacity: 0.9 - idx * 0.12,
                scale: 1 - idx * 0.02,
                x: 0,
              }}
              transition={{ type: 'spring', stiffness: 180, damping: 20, delay: idx * 0.05 }}
              className="w-[160px] p-2 rounded-lg border border-slate-900/70 bg-slate-950/85 backdrop-blur-md flex items-center justify-between gap-2 shadow-md"
            >
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-sm flex-shrink-0">{product.icon}</span>
                <div className="min-w-0">
                  <div className="text-[9px] font-bold text-white leading-tight truncate">{product.name}</div>
                  <span className="text-[7px] uppercase tracking-wider text-slate-600 font-bold">{product.category}</span>
                </div>
              </div>
              <div className="flex flex-col items-end flex-shrink-0">
                <span className="text-[9px] font-black text-green-400 font-mono">{product.score}%</span>
                <span className="text-[6px] text-slate-600 font-mono">#{idx + 1}</span>
              </div>
            </motion.div>
          ))}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
