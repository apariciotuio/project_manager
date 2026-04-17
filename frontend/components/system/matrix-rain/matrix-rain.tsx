'use client';

import { useEffect, useRef, useState } from 'react';
import { useTheme } from 'next-themes';
import { isRainEnabled } from '@/lib/theme/trinity';

// Static katakana + digit glyph pool — no interpolation from user input
const GLYPHS =
  'アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン0123456789'.split('');

const FONT_SIZE = 16;
const TARGET_FPS = 30;
const FRAME_INTERVAL = 1000 / TARGET_FPS;

function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined') return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

export function MatrixRain() {
  const { theme } = useTheme();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number>(0);
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const shouldRender =
    mounted &&
    theme === 'matrix' &&
    isRainEnabled() &&
    !prefersReducedMotion();

  useEffect(() => {
    if (!shouldRender) return;
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    function resize() {
      if (!canvas) return;
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener('resize', resize);

    const columns = Math.floor(canvas.width / FONT_SIZE);
    const drops: number[] = Array.from({ length: columns }, () =>
      Math.floor(Math.random() * -100)
    );

    let lastFrame = 0;

    function draw(now: number) {
      if (!canvas || !ctx) return;
      if (now - lastFrame < FRAME_INTERVAL) {
        rafRef.current = requestAnimationFrame(draw);
        return;
      }
      lastFrame = now;

      // Translucent black overlay → trail fade
      ctx.fillStyle = 'rgba(11, 15, 11, 0.08)';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Phosphor green glyphs
      ctx.fillStyle = 'rgba(0, 255, 65, 0.1)';
      ctx.font = `${FONT_SIZE}px ui-monospace, monospace`;

      for (let i = 0; i < drops.length; i++) {
        const glyph = GLYPHS[Math.floor(Math.random() * GLYPHS.length)] ?? '0';
        const x = i * FONT_SIZE;
        const y = (drops[i] ?? 0) * FONT_SIZE;
        ctx.fillText(glyph, x, y);

        // Reset drop when it goes off screen (randomise re-entry)
        if (y > canvas.height && Math.random() > 0.975) {
          drops[i] = 0;
        }
        drops[i] = (drops[i] ?? 0) + 1;
      }

      rafRef.current = requestAnimationFrame(draw);
    }

    rafRef.current = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(rafRef.current);
      window.removeEventListener('resize', resize);
    };
  }, [shouldRender]);

  if (!shouldRender) return null;

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 -z-10"
      style={{ opacity: 0.1 }}
    />
  );
}
