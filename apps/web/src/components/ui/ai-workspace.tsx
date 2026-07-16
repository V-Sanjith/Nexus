'use client';

import React, { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { SplineScene } from './splite';
import { PRODUCT_CATALOG, SCAN_PHASES } from './ai-workspace/product-data';
import type { HolographicProduct } from './ai-workspace/product-data';
import { NeuralCanvas } from './ai-workspace/neural-canvas';
import { AmbientParticles } from './ai-workspace/ambient-particles';
import { FloatingTags } from './ai-workspace/floating-tags';
import { StatusConsole } from './ai-workspace/status-console';
import { ProductCard } from './ai-workspace/product-card';
import { RecommendationStack } from './ai-workspace/recommendation-stack';

interface AIWorkspaceProps {
  inputValue: string;
  isAnalyzing?: boolean;
  detectedIntent?: any;
}

type ScanPhase = 'idle' | 'entering' | 'scanning' | 'scoring' | 'locked' | 'stacking';

// Generate 30 dynamic orbit positions for the Product Universe
const ORBIT_POSITIONS = Array.from({ length: 30 }).map((_, i) => {
  const angle = (i * 137.5) * (Math.PI / 180); // golden angle distribution
  const radius = 100 + (i * 8); // spiral out
  return {
    x: Math.cos(angle) * radius,
    y: Math.sin(angle) * radius,
    depth: i % 4, // 0 to 3 for varied blur/scale
  };
});

export function AIWorkspace({ inputValue, isAnalyzing = false, detectedIntent }: AIWorkspaceProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Core state
  const [activeIndex, setActiveIndex] = useState(0);
  const [scanPhase, setScanPhase] = useState<ScanPhase>('entering');
  const [animatedScore, setAnimatedScore] = useState(0);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [recommendationStack, setRecommendationStack] = useState<HolographicProduct[]>([]);
  const [statusText, setStatusText] = useState('SYS_IDLE - MONITORING INTENT');
  const [isMobile, setIsMobile] = useState(false);
  const [filteredProducts, setFilteredProducts] = useState<HolographicProduct[]>(PRODUCT_CATALOG);

  const activeProduct = filteredProducts[activeIndex % filteredProducts.length] as HolographicProduct | undefined;

  // Detect mobile
  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 768);
    check();
    window.addEventListener('resize', check);
    return () => window.removeEventListener('resize', check);
  }, []);

  // Mouse tracking (normalized -0.5 to 0.5)
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width - 0.5;
      const y = (e.clientY - rect.top) / rect.height - 0.5;
      setMousePos({ x, y });
    };

    window.addEventListener('mousemove', handleMouseMove, { passive: true });
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  // Filter products by user input
  useEffect(() => {
    if (isAnalyzing) return;

    if (!inputValue.trim()) {
      setFilteredProducts(PRODUCT_CATALOG);
      setStatusText('SYS_IDLE - MONITORING INTENT');
      return;
    }

    if (detectedIntent) {
      const cat = detectedIntent.category.toLowerCase();
      let filtered = PRODUCT_CATALOG.filter((p) => p.category === cat);
      if (filtered.length === 0) filtered = PRODUCT_CATALOG;
      
      setFilteredProducts(filtered);
      setStatusText(`MATCHING CAT: ${cat.toUpperCase()} | EVALUATING SENSORS...`);
      setActiveIndex(0);
      setScanPhase('entering');
      return;
    }

    const text = inputValue.toLowerCase();
    let filtered: HolographicProduct[] = PRODUCT_CATALOG;
    let statusMsg = 'PARSING INTENT...';

    if (text.includes('laptop') || text.includes('mac') || text.includes('gaming') || text.includes('coding') || text.includes('computer')) {
      filtered = PRODUCT_CATALOG.filter((p) => p.category === 'laptop');
      statusMsg = 'MATCHING CAT: LAPTOP | PERSONALIZING WEIGHTS...';
    } else if (text.includes('phone') || text.includes('mobile') || text.includes('iphone') || text.includes('pixel') || text.includes('samsung')) {
      filtered = PRODUCT_CATALOG.filter((p) => p.category === 'phone');
      statusMsg = 'MATCHING CAT: SMARTPHONE | EVALUATING SENSORS...';
    } else if (text.includes('monitor') || text.includes('screen') || text.includes('display') || text.includes('4k')) {
      filtered = PRODUCT_CATALOG.filter((p) => p.category === 'monitor');
      statusMsg = 'MATCHING CAT: MONITOR | CALIBRATING REFRESH...';
    } else if (text.includes('tablet') || text.includes('pad') || text.includes('ipad')) {
      filtered = PRODUCT_CATALOG.filter((p) => p.category === 'tablet');
      statusMsg = 'MATCHING CAT: TABLET | VERIFYING STYLUS...';
    } else if (text.includes('headphone') || text.includes('audio') || text.includes('sound') || text.includes('music')) {
      filtered = PRODUCT_CATALOG.filter((p) => p.category === 'headphones');
      statusMsg = 'MATCHING CAT: AUDIO | MEASURING DECI-LEVELS...';
    } else {
      statusMsg = 'PROCESSING QUERY | SCANNING MULTI-CATALOG...';
    }

    if (filtered.length === 0) filtered = PRODUCT_CATALOG;
    setFilteredProducts(filtered);
    setActiveIndex(0);
    setStatusText(statusMsg);
    setScanPhase('entering');
  }, [inputValue, isAnalyzing]);

  // Override status when analyzing (Start Decision)
  useEffect(() => {
    if (isAnalyzing) {
      setStatusText('SYS_SUBMIT - COALESCING DECISION CHANNELS...');
    }
  }, [isAnalyzing]);

  // 5-phase scan lifecycle timer
  useEffect(() => {
    if (isAnalyzing || !activeProduct) return;

    // Phase 1: Entering (0 - 0.8s)
    setScanPhase('entering');
    setAnimatedScore(0);
    setStatusText(SCAN_PHASES[0] || 'INITIALIZING...');

    const t1 = setTimeout(() => {
      // Phase 2: Scanning (0.8s - 2.5s)
      setScanPhase('scanning');
      setStatusText(SCAN_PHASES[1] || 'SCANNING...');
    }, 800);

    const t2 = setTimeout(() => {
      // Phase 3: Scoring (2.5s - 4.0s)
      setScanPhase('scoring');
      setStatusText(SCAN_PHASES[3] || 'SCORING...');
    }, 2500);

    const t3 = setTimeout(() => {
      // Phase 4: Locked (4.0s - 4.5s)
      setScanPhase('locked');
      setStatusText(`SCORE LOCKED: ${activeProduct.name} → ${activeProduct.score}%`);
    }, 4000);

    const t4 = setTimeout(() => {
      // Phase 5: Stacking (4.5s - 5.0s) → push to stack, advance index
      setScanPhase('stacking');

      setRecommendationStack((prev) => {
        const without = prev.filter((p) => p.id !== activeProduct.id);
        return [activeProduct, ...without].slice(0, 4);
      });

      // Advance to next product
      setActiveIndex((prev) => (prev + 1) % filteredProducts.length);
    }, 4500);

    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      clearTimeout(t4);
    };
  }, [activeIndex, filteredProducts, isAnalyzing]);

  // Score counter animation (0 → target)
  useEffect(() => {
    if (!activeProduct || scanPhase === 'entering') return;
    if (scanPhase !== 'scoring' && scanPhase !== 'locked') return;

    const target = activeProduct.score;
    let current = 0;
    const steps = 40;
    const stepValue = target / steps;
    const stepTime = 1400 / steps;

    const timer = setInterval(() => {
      current += stepValue;
      if (current >= target) {
        setAnimatedScore(target);
        clearInterval(timer);
      } else {
        setAnimatedScore(Math.floor(current));
      }
    }, stepTime);

    return () => clearInterval(timer);
  }, [activeProduct, scanPhase]);

  // Compute intensity for sub-components
  const intensity: 'idle' | 'typing' | 'analyzing' = isAnalyzing
    ? 'analyzing'
    : inputValue.trim()
    ? 'typing'
    : 'idle';

  // Active product tags
  const activeTags = activeProduct?.tags || [];

  // Product Universe logic
  // We duplicate the catalog to create a "universe" of products
  const allProducts = Array.from({ length: 30 }).map((_, i) => PRODUCT_CATALOG[i % PRODUCT_CATALOG.length]);
  
  // Exclude the actively highlighted product from the floating background
  const backgroundProducts = allProducts.filter((_, i) => i !== activeIndex % allProducts.length);
  const visibleFloaters = isMobile ? backgroundProducts.slice(0, 10) : backgroundProducts;

  return (
    <div
      ref={containerRef}
      className="w-full h-full relative flex items-center justify-center overflow-hidden rounded-2xl border border-slate-900/80 bg-slate-950/30 backdrop-blur-md shadow-2xl"
    >
      {/* Layer 0: Spline Robot */}
      <motion.div
        animate={{
          scale: isAnalyzing ? 1.3 : 1,
          opacity: isAnalyzing ? 0.15 : 1,
        }}
        transition={{ type: 'spring', stiffness: 80, damping: 20 }}
        className="absolute inset-0 z-0 pointer-events-auto"
      >
        <SplineScene
          scene="https://prod.spline.design/kZDDjO5HuC9GJUM2/scene.splinecode"
          className="w-full h-full object-cover"
        />
      </motion.div>

      {/* Layer 1: Neural network canvas */}
      <NeuralCanvas intensity={intensity} isMobile={isMobile} />

      {/* Layer 2: Ambient particles */}
      <AmbientParticles isMobile={isMobile} intensity={intensity} />

      {/* Layer 3: Ambient vignette + volumetric light */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,transparent_30%,rgba(2,6,23,0.85)_85%)] pointer-events-none z-[3]" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(168,85,247,0.04),transparent_50%)] pointer-events-none z-[3]" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_left,rgba(99,102,241,0.03),transparent_50%)] pointer-events-none z-[3]" />

      {/* Layer 10: Status console */}
      <StatusConsole
        statusText={statusText}
        activeCategory={activeProduct?.category || 'all'}
        productCount={filteredProducts.length}
        isActive={intensity !== 'idle'}
      />

      {/* Layer 15: Floating AI tags */}
      {!isAnalyzing && <FloatingTags activeTags={activeTags} isMobile={isMobile} />}

      {/* Layer 18-22: Product cards */}
      <div
        className="absolute inset-0 z-[18] flex items-center justify-center pointer-events-none"
        style={{ perspective: 1200 }}
      >
        {/* Active product card */}
        <AnimatePresence mode="wait">
          {!isAnalyzing && activeProduct && (
            <ProductCard
              key={activeProduct.id}
              product={activeProduct}
              isActive
              depth={0}
              positionX={0}
              positionY={0}
              mouseX={mousePos.x}
              mouseY={mousePos.y}
              scanPhase={scanPhase}
              animatedScore={animatedScore}
            />
          )}
        </AnimatePresence>

        {/* Floating non-active cards */}
        {!isAnalyzing &&
          visibleFloaters.map((p, idx) => {
            if (!p) return null;
            const orbit = ORBIT_POSITIONS[idx % ORBIT_POSITIONS.length];
            if (!orbit) return null;
            
            // Check if this product matches the current intent/filter
            const isMatching = filteredProducts.some(fp => fp.id === p.id);
            const isFaded = !isMatching && (inputValue.trim().length > 0 || detectedIntent);

            return (
              <ProductCard
                key={`${p.id}-${idx}`}
                product={p}
                isActive={false}
                isFaded={isFaded}
                depth={orbit.depth}
                positionX={orbit.x}
                positionY={orbit.y}
                mouseX={mousePos.x}
                mouseY={mousePos.y}
                scanPhase="idle"
                animatedScore={p.score}
              />
            );
          })}
      </div>

      {/* Layer 22: Recommendation stack */}
      <RecommendationStack products={recommendationStack} isMobile={isMobile} />

      {/* Analyzing overlay (Start Decision transition) */}
      <AnimatePresence>
        {isAnalyzing && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.6 }}
            className="absolute inset-0 z-[30] flex flex-col items-center justify-center gap-5 bg-slate-950/40 backdrop-blur-sm"
          >
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ repeat: Infinity, duration: 1.5, ease: 'linear' }}
              className="w-14 h-14 border-[3px] border-t-purple-500 border-r-purple-500/50 border-slate-900 rounded-full shadow-[0_0_25px_rgba(168,85,247,0.3)]"
            />
            <span className="font-mono text-xs text-purple-400 tracking-[0.2em] uppercase animate-pulse">
              COMPILING DECISION VECTOR
            </span>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
