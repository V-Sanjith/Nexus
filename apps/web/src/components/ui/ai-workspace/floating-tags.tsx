'use client';

import { useEffect, useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface FloatingTagsProps {
  activeTags: string[];
  isMobile: boolean;
}

interface TagState {
  tag: string;
  angle: number;
  radius: number;
  visible: boolean;
}

export function FloatingTags({ activeTags, isMobile }: FloatingTagsProps) {
  const maxVisible = isMobile ? 4 : 7;
  const [visibleTags, setVisibleTags] = useState<TagState[]>([]);

  // Initialize tag positions in a circle
  const tagStates = useMemo(() => {
    const selected = activeTags.slice(0, maxVisible);
    return selected.map((tag, i) => ({
      tag,
      angle: (i / selected.length) * 360,
      radius: isMobile ? 100 : 160 + (i % 3) * 30,
      visible: true,
    }));
  }, [activeTags, maxVisible, isMobile]);

  // Cycle tag visibility
  useEffect(() => {
    setVisibleTags(tagStates);

    const interval = setInterval(() => {
      setVisibleTags((prev) =>
        prev.map((t) => ({
          ...t,
          visible: Math.random() > 0.15, // 85% chance to stay visible
          angle: t.angle + 0.3, // Slow orbit
        }))
      );
    }, 3000);

    return () => clearInterval(interval);
  }, [tagStates]);

  return (
    <div className="absolute inset-0 z-[15] pointer-events-none">
      <AnimatePresence>
        {visibleTags.map((t) => {
          if (!t.visible) return null;

          const radian = (t.angle * Math.PI) / 180;
          const x = Math.cos(radian) * t.radius;
          const y = Math.sin(radian) * t.radius * 0.5; // Elliptical orbit

          return (
            <motion.div
              key={t.tag}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{
                opacity: 0.7,
                scale: 1,
                x: x,
                y: y,
              }}
              exit={{ opacity: 0, scale: 0.6 }}
              transition={{ type: 'spring', stiffness: 100, damping: 20 }}
              className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2"
            >
              <div className="px-2.5 py-1 rounded-full bg-slate-950/60 backdrop-blur-sm border border-slate-800/40 text-[9px] font-bold text-slate-400 uppercase tracking-wider whitespace-nowrap select-none">
                {t.tag}
              </div>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
