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
const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)';

export function MatrixRain() {
  const { theme } = useTheme();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number>(0);
  const [mounted, setMounted] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [rainEnabled, setRainEnabledState] = useState(false);

  useEffect(() => {
    setMounted(true);
    setRainEnabledState(isRainEnabled());
  }, []);

  // React to OS reduced-motion toggle changes
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const mq = window.matchMedia(REDUCED_MOTION_QUERY);
    setReducedMotion(mq.matches);

    function handleMotionChange(e: MediaQueryListEvent) {
      setReducedMotion(e.matches);
    }
    mq.addEventListener('change', handleMotionChange);
    return () => mq.removeEventListener('change', handleMotionChange);
  }, []);

  // React to storage changes from setRainEnabled() called in other tabs or components
  useEffect(() => {
    function handleStorage(e: StorageEvent) {
      if (e.key === 'trinity:rainEnabled') {
        setRainEnabledState(e.newValue === 'true');
      }
    }
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, []);

  const shouldRender = mounted && theme === 'matrix' && rainEnabled && !reducedMotion;

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
