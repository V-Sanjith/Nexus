'use client';

import { useMemo, useState, useEffect } from 'react';
import { motion } from 'framer-motion';

interface AmbientParticlesProps {
  isMobile: boolean;
  intensity: 'idle' | 'typing' | 'analyzing';
}

export function AmbientParticles({ isMobile, intensity }: AmbientParticlesProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const count = isMobile ? 8 : (intensity === 'analyzing' ? 25 : 18);

  const particles = useMemo(() => {
    if (!mounted) return [];
    return Array.from({ length: count }, (_, i) => ({
      id: i,
      x: Math.random() * 100,
      y: Math.random() * 100,
      size: Math.random() * 2.5 + 1.5,
      duration: 8 + Math.random() * 12,
      delay: Math.random() * 5,
      opacity: 0.04 + Math.random() * 0.1,
    }));
  }, [count, mounted]);

  if (!mounted) {
    return null;
  }

  return (
    <div className="absolute inset-0 z-[2] pointer-events-none overflow-hidden">
      {particles.map((p) => (
        <motion.div
          key={p.id}
          className="absolute rounded-full"
          style={{
            width: p.size,
            height: p.size,
            left: `${p.x}%`,
            top: `${p.y}%`,
            background: intensity === 'idle'
              ? 'rgba(129, 140, 248, 0.6)'
              : 'rgba(192, 132, 252, 0.6)',
          }}
          animate={{
            y: [0, -30, -60, -30, 0],
            x: [0, 8, -5, 12, 0],
            opacity: [p.opacity, p.opacity * 1.5, p.opacity * 0.5, p.opacity * 1.2, p.opacity],
          }}
          transition={{
            duration: p.duration,
            repeat: Infinity,
            delay: p.delay,
            ease: 'linear',
          }}
        />
      ))}
    </div>
  );
}
