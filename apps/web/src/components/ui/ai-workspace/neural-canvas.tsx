'use client';

import { useEffect, useRef } from 'react';

interface NeuralCanvasProps {
  intensity: 'idle' | 'typing' | 'analyzing';
  isMobile: boolean;
}

export function NeuralCanvas({ intensity, isMobile }: NeuralCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId: number;
    let width = (canvas.width = canvas.offsetWidth);
    let height = (canvas.height = canvas.offsetHeight);

    const handleResize = () => {
      if (!canvas) return;
      width = canvas.width = canvas.offsetWidth;
      height = canvas.height = canvas.offsetHeight;
    };
    window.addEventListener('resize', handleResize);

    // Node class for the neural network
    class Node {
      x: number;
      y: number;
      vx: number;
      vy: number;
      radius: number;
      pulsePhase: number;

      constructor() {
        this.x = Math.random() * width;
        this.y = Math.random() * height;
        this.vx = (Math.random() - 0.5) * 0.3;
        this.vy = (Math.random() - 0.5) * 0.3;
        this.radius = Math.random() * 1.5 + 0.8;
        this.pulsePhase = Math.random() * Math.PI * 2;
      }

      update(speed: number, time: number) {
        this.x += this.vx * speed;
        this.y += this.vy * speed;
        // Soft pulse
        this.radius = (Math.random() * 0.5 + 1) + Math.sin(time * 0.001 + this.pulsePhase) * 0.3;

        if (this.x < 0 || this.x > width) this.vx *= -1;
        if (this.y < 0 || this.y > height) this.vy *= -1;
      }

      draw(context: CanvasRenderingContext2D, color: string) {
        context.beginPath();
        context.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
        context.fillStyle = color;
        context.fill();
      }
    }

    // Configure based on intensity and device
    const nodesCount = isMobile ? 22 : (intensity === 'analyzing' ? 65 : (intensity === 'typing' ? 50 : 40));
    const nodesList: Node[] = [];
    for (let i = 0; i < nodesCount; i++) {
      nodesList.push(new Node());
    }

    // Signal packets traveling between nodes
    const packets: { fromX: number; fromY: number; toX: number; toY: number; progress: number; speed: number }[] = [];

    const render = (time: number) => {
      ctx.clearRect(0, 0, width, height);

      const speedMultiplier = intensity === 'analyzing' ? 6.0 : (intensity === 'typing' ? 2.5 : 1.0);
      const nodeColor = intensity === 'analyzing'
        ? 'rgba(168, 85, 247, 0.5)'
        : (intensity === 'typing' ? 'rgba(168, 85, 247, 0.35)' : 'rgba(99, 102, 241, 0.25)');
      const lineColor = intensity === 'analyzing'
        ? 'rgba(168, 85, 247, 0.12)'
        : (intensity === 'typing' ? 'rgba(168, 85, 247, 0.08)' : 'rgba(99, 102, 241, 0.05)');

      // Update and draw nodes
      for (const node of nodesList) {
        node.update(speedMultiplier, time);
        node.draw(ctx, nodeColor);
      }

      // Draw connections (only nearby)
      const connectionDist = 120;
      for (let i = 0; i < nodesCount; i++) {
        for (let j = i + 1; j < nodesCount; j++) {
          const nodeI = nodesList[i];
          const nodeJ = nodesList[j];
          if (nodeI && nodeJ) {
            const dx = nodeI.x - nodeJ.x;
            const dy = nodeI.y - nodeJ.y;
            const dist = Math.sqrt(dx * dx + dy * dy);

            if (dist < connectionDist) {
              ctx.beginPath();
              ctx.moveTo(nodeI.x, nodeI.y);
              ctx.lineTo(nodeJ.x, nodeJ.y);
              ctx.strokeStyle = lineColor;
              ctx.lineWidth = (1 - dist / connectionDist) * 0.8;
              ctx.stroke();
            }
          }
        }
      }

      // Spawn signal packets occasionally
      const spawnRate = intensity === 'analyzing' ? 0.06 : (intensity === 'typing' ? 0.025 : 0.008);
      if (Math.random() < spawnRate && packets.length < 8) {
        const fromNode = nodesList[Math.floor(Math.random() * nodesCount)];
        const toNode = nodesList[Math.floor(Math.random() * nodesCount)];
        if (fromNode && toNode && fromNode !== toNode) {
          packets.push({
            fromX: fromNode.x,
            fromY: fromNode.y,
            toX: toNode.x,
            toY: toNode.y,
            progress: 0,
            speed: 0.015 + Math.random() * 0.01,
          });
        }
      }

      // Draw and update signal packets
      for (let i = packets.length - 1; i >= 0; i--) {
        const pkt = packets[i];
        if (!pkt) continue;
        pkt.progress += pkt.speed * speedMultiplier;
        if (pkt.progress >= 1) {
          packets.splice(i, 1);
          continue;
        }

        const px = pkt.fromX + (pkt.toX - pkt.fromX) * pkt.progress;
        const py = pkt.fromY + (pkt.toY - pkt.fromY) * pkt.progress;

        ctx.beginPath();
        ctx.arc(px, py, 2.5, 0, Math.PI * 2);
        ctx.fillStyle = intensity === 'idle' ? '#818cf8' : '#c084fc';
        ctx.shadowBlur = 8;
        ctx.shadowColor = intensity === 'idle' ? '#6366f1' : '#a855f7';
        ctx.fill();
        ctx.shadowBlur = 0;
      }

      animationFrameId = requestAnimationFrame(render);
    };

    animationFrameId = requestAnimationFrame(render);

    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animationFrameId);
    };
  }, [intensity, isMobile]);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 z-[1] pointer-events-none"
      style={{ opacity: 0.1 }}
    />
  );
}
