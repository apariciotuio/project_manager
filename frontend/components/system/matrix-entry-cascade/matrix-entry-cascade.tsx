'use client';

/**
 * MatrixEntryCascade — one-shot falling-glyph overlay triggered on inbound
 * Matrix mode transition.
 *
 * Refactor TODO: extract shared drawing primitive with MatrixRain into
 * `matrix-canvas.ts` parameterized by `mode: 'burst' | 'loop'` once both
 * components stabilise.
 */

import { useEffect, useRef, useCallback } from 'react';

// Duration of the cascade in milliseconds
const CASCADE_DURATION_MS = 1600;

// Font size & spacing — columns are packed one per FONT_SIZE of horizontal space
// so the screen fills densely, matching the classic Matrix rain look.
const FONT_SIZE = 16;

// Stream length bounds (glyphs per column)
const MIN_STREAM_LEN = 10;
const MAX_STREAM_LEN = 28;

// Speed variation: ±40% around BASE_SPEED (px per frame at 60fps)
const BASE_SPEED = 14;
const SPEED_VARIATION = 0.4;

// Phosphor green palette
const COLOR_LEAD = '#AAFFAA';
const COLOR_TRAIL = '#00FF41';

// Font matching the Matrix theme monospace stack
const FONT = `${FONT_SIZE}px ui-monospace, "Cascadia Code", "Courier New", monospace`;

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
  // Latest-callback pattern: capture onComplete in a ref so the main effect
  // never needs onComplete in its dependency array, preventing re-triggers when
  // the parent re-renders with a new inline callback reference.
  const onCompleteRef = useRef(onComplete);
  useEffect(() => {
    onCompleteRef.current = onComplete;
  });

  const runCascade = useCallback(() => {
    // SSR guard
    if (typeof window === 'undefined') return;
    if (prefersReducedMotion()) {
      onCompleteRef.current?.();
      return;
    }

    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Size canvas to full viewport
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;

    // Paint opaque black backdrop once — the per-frame fade below keeps it dark
    // so the underlying page is hidden while the cascade plays.
    ctx.fillStyle = '#000000';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // One column per FONT_SIZE of horizontal space — dense coverage.
    const colCount = Math.max(1, Math.floor(canvas.width / FONT_SIZE));
    const colSpacing = canvas.width / colCount;

    const columns: Column[] = Array.from({ length: colCount }, (_, i) => {
      const streamLen = MIN_STREAM_LEN + Math.floor(Math.random() * (MAX_STREAM_LEN - MIN_STREAM_LEN + 1));
      const speed = BASE_SPEED * (1 + (Math.random() * 2 - 1) * SPEED_VARIATION);
      return {
        x: i * colSpacing + colSpacing / 2,
        // Stagger column starts so the wavefront sweeps across the screen
        // rather than arriving uniformly.
        y: -(Math.random() * canvas.height * 0.8 + streamLen * FONT_SIZE),
        speed,
        glyphs: Array.from({ length: streamLen }, randomGlyph),
        streamLen,
      };
    });

    const startTime = performance.now();

    function draw(now: number) {
      if (!canvas || !ctx) return;

      const elapsed = now - startTime;

      // Semi-opaque black overlay fades prior frames (classic Matrix trail).
      ctx.fillStyle = 'rgba(0, 0, 0, 0.12)';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      ctx.font = FONT;
      ctx.textBaseline = 'top';

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
        onCompleteRef.current?.();
      }
    }

    rafRef.current = requestAnimationFrame(draw);
  }, []);

  useEffect(() => {
    if (!active) return;
    runCascade();
    return () => {
      cancelAnimationFrame(rafRef.current);
    };
  }, [active, runCascade]);

  if (!active) return null;

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className="pointer-events-none fixed inset-0"
      style={{ zIndex: 9999 }}
    />
  );
}
