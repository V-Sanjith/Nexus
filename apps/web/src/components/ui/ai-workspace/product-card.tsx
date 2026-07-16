'use client';

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import type { HolographicProduct } from './product-data';

interface ProductCardProps {
  product: HolographicProduct;
  isActive: boolean;
  isFaded?: boolean;
  depth: number; // 0 = foreground, 1 = mid, 2 = background
  positionX: number;
  positionY: number;
  mouseX: number;
  mouseY: number;
  scanPhase: 'idle' | 'entering' | 'scanning' | 'scoring' | 'locked' | 'stacking';
  animatedScore: number;
  onHover?: () => void;
  onClick?: () => void;
}

export function ProductCard({
  product,
  isActive,
  isFaded = false,
  depth,
  positionX,
  positionY,
  mouseX,
  mouseY,
  scanPhase,
  animatedScore,
  onHover,
  onClick,
}: ProductCardProps) {
  const [tilt, setTilt] = useState({ x: 0, y: 0 });
  const [isHovered, setIsHovered] = useState(false);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width - 0.5;
    const y = (e.clientY - rect.top) / rect.height - 0.5;
    setTilt({ x: x * 12, y: -y * 12 });
  };

  const handleMouseLeave = () => {
    setTilt({ x: 0, y: 0 });
    setIsHovered(false);
  };

  const handleMouseEnter = () => {
    setIsHovered(true);
    onHover?.();
  };

  // Depth-based visual properties
  const blurAmount = isActive ? 0 : isFaded ? 5 : depth === 0 ? 0.5 : depth === 1 ? 1.5 : 2.5;
  const opacityValue = isActive ? 1 : isFaded ? 0.05 : depth === 0 ? 0.7 : depth === 1 ? 0.5 : 0.35;
  const scaleValue = isActive ? 1 : isFaded ? 0.5 : 0.75 - depth * 0.06;

  // Parallax offset based on depth and mouse
  const parallaxX = positionX + mouseX * (30 - depth * 8);
  const parallaxY = positionY + mouseY * (30 - depth * 8);

  if (isActive) {
    // Active card: centered, full detail, scan overlay
    return (
      <motion.div
        layoutId={`card-${product.id}`}
        initial={{ opacity: 0, scale: 0.7, y: 40 }}
        animate={{
          opacity: 1,
          scale: 1,
          x: mouseX * 15,
          y: mouseY * 15,
          rotateY: tilt.x,
          rotateX: tilt.y,
          z: 0,
          boxShadow: isHovered 
            ? '0 0 50px rgba(168, 85, 247, 0.25)' 
            : '0 0 30px rgba(99, 102, 241, 0.08)'
        }}
        exit={{ opacity: 0, scale: 0.7, y: -30 }}
        whileTap={{ scale: 0.97 }}
        transition={{ type: 'spring', stiffness: 200, damping: 20, mass: 0.8 }}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        onMouseEnter={handleMouseEnter}
        onClick={onClick}
        className={`absolute left-6 md:left-10 bottom-6 md:bottom-10 w-[220px] md:w-[260px] p-4 md:p-5 rounded-xl border bg-slate-950/80 backdrop-blur-xl pointer-events-auto cursor-pointer z-[22] ${
          isHovered ? 'border-purple-500/40' : 'border-indigo-500/20'
        }`}
        style={{ transformStyle: 'preserve-3d' }}
      >
        {/* Scan laser */}
        {(scanPhase === 'scanning' || scanPhase === 'scoring') && (
          <div className="absolute inset-0 rounded-xl overflow-hidden pointer-events-none">
            <motion.div
              initial={{ y: '-100%' }}
              animate={{ y: '250%' }}
              transition={{ repeat: Infinity, duration: 2.2, ease: 'linear' }}
              className="w-full h-[2px] bg-gradient-to-r from-transparent via-purple-400 to-transparent shadow-[0_0_12px_#a855f7] opacity-70"
            />
          </div>
        )}

        {/* Wireframe overlay during scan */}
        {scanPhase === 'scanning' && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.04 }}
            className="absolute inset-0 rounded-xl pointer-events-none"
            style={{
              backgroundImage: `
                linear-gradient(rgba(168,85,247,0.3) 1px, transparent 1px),
                linear-gradient(90deg, rgba(168,85,247,0.3) 1px, transparent 1px)
              `,
              backgroundSize: '20px 20px',
            }}
          />
        )}

        {/* Header: icon + name + score */}
        <div className="flex items-center justify-between border-b border-slate-800/60 pb-3 mb-3">
          <div className="flex items-center gap-2">
            <span className="text-xl">{product.icon}</span>
            <div>
              <h4 className="text-[13px] font-bold text-white tracking-tight leading-tight">{product.name}</h4>
              <span className="text-[8px] uppercase tracking-wider text-indigo-400/80 font-semibold">
                {product.category}
              </span>
            </div>
          </div>

          {/* Radial score */}
          <div className="relative w-10 h-10 flex items-center justify-center">
            <svg className="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
              <path
                className="text-slate-900"
                strokeWidth="3"
                stroke="currentColor"
                fill="none"
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              />
              <path
                className={animatedScore >= product.score ? 'text-green-400' : 'text-indigo-400'}
                strokeDasharray={`${animatedScore}, 100`}
                strokeWidth="3"
                strokeLinecap="round"
                stroke="currentColor"
                fill="none"
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              />
            </svg>
            <div className="absolute text-[9px] font-black text-white font-mono">
              {animatedScore}%
            </div>
          </div>
        </div>

        {/* Spec chips */}
        <div className="flex flex-col gap-2">
          {product.specs.map((spec, idx) => (
            <motion.div
              key={spec.label}
              initial={{ opacity: 0, x: -12 }}
              animate={{
                opacity: scanPhase === 'entering' ? 0 : 1,
                x: 0,
              }}
              transition={{ delay: 0.15 + idx * 0.1, type: 'spring', stiffness: 200, damping: 20 }}
              className="flex items-center justify-between text-[11px]"
            >
              <span className="text-slate-500 font-medium">{spec.label}</span>
              <div className="flex items-center gap-1.5 font-semibold text-white">
                <span>{spec.value}</span>
                <motion.span
                  initial={{ scale: 0 }}
                  animate={{ scale: scanPhase === 'entering' ? 0 : 1 }}
                  transition={{ delay: 0.4 + idx * 0.12, type: 'spring', stiffness: 300 }}
                  className={`text-[10px] ${spec.status === 'passed' ? 'text-green-400' : 'text-amber-400'}`}
                >
                  {spec.status === 'passed' ? '✓' : '⚠'}
                </motion.span>
              </div>
            </motion.div>
          ))}
        </div>

        {/* Price and status */}
        <div className="mt-3 pt-2.5 border-t border-slate-800/50 flex items-center justify-between text-[10px]">
          <span className="text-slate-300 font-bold">{product.price}</span>
          <span
            className={`px-2 py-0.5 rounded font-bold uppercase tracking-wider ${
              scanPhase === 'locked'
                ? 'bg-green-500/10 border border-green-500/20 text-green-400'
                : 'bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 animate-pulse'
            }`}
          >
            {scanPhase === 'locked' ? 'SCORED' : scanPhase === 'scanning' ? 'SCANNING' : 'ANALYZING'}
          </span>
        </div>
      </motion.div>
    );
  }

  // Non-active floating card
  return (
    <motion.div
      layoutId={`card-${product.id}`}
      animate={{
        opacity: opacityValue,
        scale: scaleValue,
        x: parallaxX,
        y: parallaxY,
        z: -80 * (depth + 1),
        rotateY: positionX > 0 ? -8 : 8,
      }}
      transition={{ type: 'spring', stiffness: 150, damping: 25 }}
      whileHover={{ scale: scaleValue + 0.08, opacity: Math.min(opacityValue + 0.2, 1), zIndex: 30 }}
      whileTap={{ scale: scaleValue - 0.05 }}
      onMouseEnter={handleMouseEnter}
      onClick={onClick}
      className="absolute w-[110px] md:w-[130px] p-2.5 md:p-3 rounded-lg border border-slate-900/60 hover:border-indigo-500/30 hover:bg-slate-900/60 hover:shadow-[0_0_20px_rgba(99,102,241,0.15)] bg-slate-950/50 backdrop-blur-sm flex flex-col items-center gap-1.5 select-none pointer-events-auto cursor-pointer z-[18] transition-colors"
      style={{
        filter: `blur(${blurAmount}px)`,
        transformStyle: 'preserve-3d',
      }}
    >
      <span className="text-lg md:text-xl">{product.icon}</span>
      <span className="text-[9px] md:text-[10px] font-bold text-slate-400 text-center leading-tight truncate w-full">
        {product.name}
      </span>
      <div className="flex items-center gap-1">
        <span className="text-[7px] md:text-[8px] font-mono text-indigo-500/60 font-semibold">{product.score}%</span>
        <span className="text-[7px] text-slate-600">•</span>
        <span className="text-[7px] text-slate-500 truncate">{product.price}</span>
      </div>
    </motion.div>
  );
}
