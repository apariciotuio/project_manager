'use client';

import { useState, useEffect, useRef } from 'react';

/**
 * Returns a human-readable relative time string for the given ISO date.
 * Re-renders at 1 Hz. Respects prefers-reduced-motion (stops updating if true).
 */
export function useRelativeTime(iso: string): string {
  const [label, setLabel] = useState(() => formatRelative(iso));
  const reducedMotion = useRef(false);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      reducedMotion.current = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }
    if (reducedMotion.current) return;

    const id = setInterval(() => {
      setLabel(formatRelative(iso));
    }, 1000);

    return () => clearInterval(id);
  }, [iso]);

  return label;
}

export function formatRelative(iso: string): string {
  const now = Date.now();
  const then = new Date(iso).getTime();
  const diff = now - then;
  const abs = Math.abs(diff);
  const future = diff < 0;

  if (abs < 10_000) return 'ahora mismo';

  const seconds = Math.floor(abs / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);
  const weeks = Math.floor(days / 7);
  const months = Math.floor(days / 30);
  const years = Math.floor(days / 365);

  function ago(n: number, unit: string): string {
    return future ? `en ${n} ${unit}` : `hace ${n} ${unit}`;
  }

  if (seconds < 60) return ago(seconds, seconds === 1 ? 'segundo' : 'segundos');
  if (minutes < 60) return ago(minutes, minutes === 1 ? 'minuto' : 'minutos');
  if (hours < 24) return ago(hours, hours === 1 ? 'hora' : 'horas');
  if (days < 7) return ago(days, days === 1 ? 'día' : 'días');
  if (weeks < 5) return ago(weeks, weeks === 1 ? 'semana' : 'semanas');
  if (months < 12) return ago(months, months === 1 ? 'mes' : 'meses');
  return ago(years, years === 1 ? 'año' : 'años');
}
