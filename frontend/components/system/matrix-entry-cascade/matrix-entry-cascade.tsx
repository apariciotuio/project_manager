'use client';

/**
 * MatrixEntryCascade — one-shot falling-glyph overlay triggered on inbound
 * Matrix mode transition.
 *
 * Refactor TODO: extract shared drawing primitive with MatrixRain into
 * `matrix-canvas.ts` parameterized by `mode: 'burst' | 'loop'` once both
 * components stabilise.
 */

import { useEffect, useRef } from 'react';

// Duration of the cascade in milliseconds
const CASCADE_DURATION_MS = 1200;

// Column count bounds
const MIN_COLUMNS = 10;
const MAX_COLUMNS = 15;

// Stream length bounds (glyphs per column)
const MIN_STREAM_LEN = 8;
const MAX_STREAM_LEN = 20;

// Speed variation: ±30% around BASE_SPEED (px per frame at 60fps)
const BASE_SPEED = 18;
const SPEED_VARIATION = 0.3;

// Phosphor green palette
const COLOR_LEAD = '#AAFFAA';
const COLOR_TRAIL = '#00FF41';

// Font matching the Matrix theme monospace stack
const FONT = '16px ui-monospace, "Cascadia Code", "Courier New", monospace';

// Glyph pool: half-width katakana U+FF66–U+FF9D + digits
const GLYPH_POOL: string[] = [];
for (let cp = 0xff66; cp <= 0xff9d; cp++) {
  GLYPH_POOL.push(String.fromCodePoint(cp));
}
for (let d = 0; d <= 9; d++) {
  GLYPH_POOL.push(String(d));
}

function randomGlyph(): string {
  return GLYPH_POOL[Math.floor(Math.random() * GLYPH_POOL.length)] ?? '0';
}

function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined') return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

interface Column {
  x: number;
  y: number;
  speed: number;
  glyphs: string[];
  streamLen: number;
}

interface MatrixEntryCascadeProps {
  /** Whether the cascade should play. Toggling to false aborts cleanly. */
  active: boolean;
  /** Called when the cascade finishes naturally (not on abort). */
  onComplete?: () => void;
}

export function MatrixEntryCascade({ active, onComplete }: MatrixEntryCascadeProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    if (!active) return;

    // SSR guard + reduced-motion skip
    if (typeof window === 'undefined') return;
    if (prefersReducedMotion()) {
      onComplete?.();
      return;
    }

    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Size canvas to full viewport
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;

    const colCount = MIN_COLUMNS + Math.floor(Math.random() * (MAX_COLUMNS - MIN_COLUMNS + 1));
    const colSpacing = canvas.width / colCount;

    const columns: Column[] = Array.from({ length: colCount }, (_, i) => {
      const streamLen = MIN_STREAM_LEN + Math.floor(Math.random() * (MAX_STREAM_LEN - MIN_STREAM_LEN + 1));
      const speed = BASE_SPEED * (1 + (Math.random() * 2 - 1) * SPEED_VARIATION);
      return {
        x: i * colSpacing + colSpacing / 2,
        y: -(streamLen * 16 + Math.random() * canvas.height * 0.5),
        speed,
        glyphs: Array.from({ length: streamLen }, randomGlyph),
        streamLen,
      };
    });

    const startTime = performance.now();
    const FONT_SIZE = 16;

    function draw(now: number) {
      if (!canvas || !ctx) return;

      const elapsed = now - startTime;

      // Clear to transparent each frame (not additive — burst mode)
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      ctx.font = FONT;

      for (const col of columns) {
        // Advance position
        col.y += col.speed;

        for (let j = 0; j < col.glyphs.length; j++) {
          const glyphY = col.y - j * FONT_SIZE;
          if (glyphY < -FONT_SIZE || glyphY > canvas.height) continue;

          // Randomly mutate glyphs for the flickering effect
          if (Math.random() < 0.05) {
            col.glyphs[j] = randomGlyph();
          }

          // Lead glyph (j === 0) is brighter
          ctx.fillStyle = j === 0 ? COLOR_LEAD : COLOR_TRAIL;
          ctx.globalAlpha = j === 0 ? 1 : Math.max(0.1, 1 - j / col.glyphs.length);
          ctx.fillText(col.glyphs[j] ?? '0', col.x, glyphY);
        }
        ctx.globalAlpha = 1;
      }

      if (elapsed < CASCADE_DURATION_MS) {
        rafRef.current = requestAnimationFrame(draw);
      } else {
        // Cascade complete — clean up
        onComplete?.();
      }
    }

    rafRef.current = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(rafRef.current);
    };
  }, [active, onComplete]);

  if (!active) return null;
  if (typeof window !== 'undefined' && prefersReducedMotion()) return null;

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className="pointer-events-none fixed inset-0"
      style={{ zIndex: 9999 }}
    />
  );
}
