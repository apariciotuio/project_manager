/**
 * ColorPicker — preset palette (12 swatches) + custom hex input.
 *
 * role="radiogroup" — keyboard navigable (arrow keys, Enter/Space, Tab).
 * Each swatch: aria-label with human-readable color name, aria-checked.
 * Works in light, dark, and matrix themes — selection ring uses CSS ring token.
 *
 * Usage:
 *   <ColorPicker value={color} onChange={setColor} />
 *
 * F-9 (EP-21). NOT wired into any form yet — F-10 (Wave 3) will consume it.
 */

'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';

// ─── Preset palette ──────────────────────────────────────────────────────────
// 12 mid-tone colors aligned with Tailwind's default 500 palette.
// Exported so tests can import and assert count + names.

export interface PresetColor {
  name: string;
  hex: string;
}

export const PRESET_COLORS: PresetColor[] = [
  { name: 'Red', hex: '#ef4444' },
  { name: 'Orange', hex: '#f97316' },
  { name: 'Amber', hex: '#f59e0b' },
  { name: 'Yellow', hex: '#eab308' },
  { name: 'Green', hex: '#22c55e' },
  { name: 'Emerald', hex: '#10b981' },
  { name: 'Teal', hex: '#14b8a6' },
  { name: 'Cyan', hex: '#06b6d4' },
  { name: 'Blue', hex: '#3b82f6' },
  { name: 'Indigo', hex: '#6366f1' },
  { name: 'Purple', hex: '#a855f7' },
  { name: 'Pink', hex: '#ec4899' },
];

const HEX_REGEX = /^#[0-9a-fA-F]{6}$/;
const DEBOUNCE_MS = 150;

function isPresetHex(hex: string | undefined): boolean {
  return PRESET_COLORS.some((p) => p.hex === hex);
}

// ─── Component ───────────────────────────────────────────────────────────────

interface ColorPickerProps {
  value?: string;
  onChange: (value: string | undefined) => void;
  className?: string;
}

export function ColorPicker({ value, onChange, className }: ColorPickerProps) {
  // Custom mode: active when value is set to a non-preset hex,
  // OR when user explicitly clicked "Custom" (tracked by customMode state).
  const valueIsCustomHex = value !== undefined && !isPresetHex(value);
  const [customMode, setCustomMode] = useState(valueIsCustomHex);
  const isCustomActive = customMode || valueIsCustomHex;

  const [customInput, setCustomInput] = useState(valueIsCustomHex ? (value ?? '') : '');
  const [customError, setCustomError] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Sync customInput when an external non-preset value arrives
  useEffect(() => {
    if (value && !isPresetHex(value)) {
      setCustomInput(value);
      setCustomMode(true);
    }
  }, [value]);

  // ── Preset handlers ────────────────────────────────────────────────────────

  const handlePresetClick = useCallback(
    (hex: string) => {
      if (value === hex) {
        // Toggle off — clear selection
        onChange(undefined);
      } else {
        onChange(hex);
        setCustomMode(false);
        setCustomError(null);
      }
    },
    [onChange, value],
  );

  // ── Custom handlers ────────────────────────────────────────────────────────

  const handleCustomClick = useCallback(() => {
    setCustomMode(true);
    // If there was a preset selected, clear it so custom takes over
    if (value && isPresetHex(value)) {
      onChange(undefined);
    }
  }, [onChange, value]);

  const handleCustomChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const raw = e.target.value;
      setCustomInput(raw);
      setCustomError(null);

      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        if (HEX_REGEX.test(raw)) {
          onChange(raw);
          setCustomError(null);
        } else if (raw.trim() !== '') {
          setCustomError('Enter a valid hex color, e.g. #3b82f6');
        }
      }, DEBOUNCE_MS);
    },
    [onChange],
  );

  // ── Keyboard navigation ────────────────────────────────────────────────────
  // Indexes 0..11 = presets, 12 = Custom

  const radioRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLButtonElement>, index: number) => {
      const total = PRESET_COLORS.length + 1; // +1 for Custom
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        e.preventDefault();
        const next = (index + 1) % total;
        radioRefs.current[next]?.focus();
      } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        e.preventDefault();
        const prev = (index - 1 + total) % total;
        radioRefs.current[prev]?.focus();
      }
    },
    [],
  );

  const handlePresetKeyActivate = useCallback(
    (e: React.KeyboardEvent<HTMLButtonElement>, hex: string) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        handlePresetClick(hex);
      }
    },
    [handlePresetClick],
  );

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div
      role="radiogroup"
      aria-label="Color"
      className={cn('flex flex-col gap-3', className)}
    >
      {/* Preset swatches + Custom option in one row */}
      <div className="flex flex-wrap gap-2">
        {PRESET_COLORS.map((preset, index) => {
          const isSelected = value === preset.hex;
          return (
            <button
              key={preset.hex}
              ref={(el) => { radioRefs.current[index] = el; }}
              type="button"
              role="radio"
              aria-label={preset.name}
              aria-checked={isSelected}
              onClick={() => handlePresetClick(preset.hex)}
              onKeyDown={(e) => {
                handleKeyDown(e, index);
                handlePresetKeyActivate(e, preset.hex);
              }}
              className={cn(
                'h-7 w-7 rounded-full border-2 transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
                isSelected
                  ? 'scale-110 border-ring shadow-md'
                  : 'border-transparent hover:scale-105 hover:border-ring/50',
              )}
              style={{ backgroundColor: preset.hex }}
            />
          );
        })}

        {/* Custom radio */}
        <button
          ref={(el) => { radioRefs.current[PRESET_COLORS.length] = el; }}
          type="button"
          role="radio"
          aria-label="Custom"
          aria-checked={isCustomActive}
          onClick={handleCustomClick}
          onKeyDown={(e) => handleKeyDown(e, PRESET_COLORS.length)}
          className={cn(
            'h-7 rounded-full border-2 px-2 text-xs transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
            isCustomActive
              ? 'scale-105 border-ring bg-accent text-accent-foreground'
              : 'border-dashed border-border text-muted-foreground hover:border-ring/50',
          )}
        >
          Custom
        </button>
      </div>

      {/* Custom hex input — visible when custom mode is active */}
      {isCustomActive && (
        <div className="flex flex-col gap-1">
          <input
            type="text"
            value={customInput}
            onChange={handleCustomChange}
            placeholder="#rrggbb"
            maxLength={7}
            className={cn(
              'h-9 w-36 rounded-md border px-3 font-mono text-body-sm focus:outline-none focus:ring-2 focus:ring-ring',
              customError
                ? 'border-destructive focus:ring-destructive'
                : 'border-input bg-background text-foreground',
            )}
            aria-invalid={customError !== null}
            aria-describedby={customError ? 'color-picker-error' : undefined}
          />
          {customError && (
            <p
              id="color-picker-error"
              role="alert"
              className="text-body-sm text-destructive"
            >
              {customError}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
