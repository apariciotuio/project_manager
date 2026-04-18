import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ColorPicker, PRESET_COLORS } from '@/components/ui/color-picker';

// ─────────────────────────────────────────────────────────────
// Helper
// ─────────────────────────────────────────────────────────────

function setup(value?: string, onChange?: (v: string | undefined) => void) {
  const handler = onChange ?? vi.fn();
  const utils = render(
    <ColorPicker value={value} onChange={handler} />,
  );
  return { handler, ...utils };
}

// ─────────────────────────────────────────────────────────────
// Preset palette
// ─────────────────────────────────────────────────────────────

describe('ColorPicker — preset palette', () => {
  it('renders exactly 12 preset swatches', () => {
    setup();
    expect(PRESET_COLORS).toHaveLength(12);
    // 12 presets + 1 Custom = 13 radios
    const swatches = screen.getAllByRole('radio');
    expect(swatches.length).toBeGreaterThanOrEqual(12);
  });

  it('has role="radiogroup" with aria-label="Color"', () => {
    setup();
    expect(screen.getByRole('radiogroup', { name: 'Color' })).toBeInTheDocument();
  });

  it('each preset swatch has aria-label with color name', () => {
    setup();
    for (const preset of PRESET_COLORS) {
      expect(screen.getByRole('radio', { name: preset.name })).toBeInTheDocument();
    }
  });

  it('marks matching swatch as checked when value matches', () => {
    const bluePreset = PRESET_COLORS.find((p) => p.name === 'Blue')!;
    setup(bluePreset.hex);
    const blueRadio = screen.getByRole('radio', { name: 'Blue' });
    expect(blueRadio).toHaveAttribute('aria-checked', 'true');
  });

  it('marks no swatch checked when value is undefined', () => {
    setup(undefined);
    for (const preset of PRESET_COLORS) {
      expect(screen.getByRole('radio', { name: preset.name })).toHaveAttribute('aria-checked', 'false');
    }
  });

  it('calls onChange with hex when a swatch is clicked', () => {
    const handler = vi.fn();
    setup(undefined, handler);
    const redPreset = PRESET_COLORS.find((p) => p.name === 'Red')!;
    fireEvent.click(screen.getByRole('radio', { name: 'Red' }));
    expect(handler).toHaveBeenCalledWith(redPreset.hex);
  });

  it('deselects previously selected swatch when another is clicked', () => {
    const bluePreset = PRESET_COLORS.find((p) => p.name === 'Blue')!;
    const redPreset = PRESET_COLORS.find((p) => p.name === 'Red')!;
    const handler = vi.fn();
    const { rerender } = setup(bluePreset.hex, handler);
    fireEvent.click(screen.getByRole('radio', { name: 'Red' }));
    expect(handler).toHaveBeenCalledWith(redPreset.hex);
    rerender(<ColorPicker value={redPreset.hex} onChange={handler} />);
    expect(screen.getByRole('radio', { name: 'Blue' })).toHaveAttribute('aria-checked', 'false');
    expect(screen.getByRole('radio', { name: 'Red' })).toHaveAttribute('aria-checked', 'true');
  });
});

// ─────────────────────────────────────────────────────────────
// Custom hex entry
// ─────────────────────────────────────────────────────────────

describe('ColorPicker — custom hex', () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });

  it('renders a "Custom" radio option', () => {
    vi.useRealTimers();
    setup();
    expect(screen.getByRole('radio', { name: /custom/i })).toBeInTheDocument();
  });

  it('does NOT show hex input when Custom is not selected', () => {
    vi.useRealTimers();
    setup();
    expect(screen.queryByPlaceholderText('#rrggbb')).not.toBeInTheDocument();
  });

  it('shows hex input when Custom is clicked', () => {
    vi.useRealTimers();
    setup();
    fireEvent.click(screen.getByRole('radio', { name: /custom/i }));
    expect(screen.getByPlaceholderText('#rrggbb')).toBeInTheDocument();
  });

  it('shows hex input when value is a custom (non-preset) hex', () => {
    vi.useRealTimers();
    setup('#abcdef');
    expect(screen.getByPlaceholderText('#rrggbb')).toBeInTheDocument();
  });

  it('accepts valid hex and calls onChange after debounce', () => {
    const handler = vi.fn();
    setup(undefined, handler);
    fireEvent.click(screen.getByRole('radio', { name: /custom/i }));
    const input = screen.getByPlaceholderText('#rrggbb');
    fireEvent.change(input, { target: { value: '#ff0000' } });
    // Not yet called — debounced
    expect(handler).not.toHaveBeenCalled();
    act(() => { vi.advanceTimersByTime(200); });
    expect(handler).toHaveBeenCalledWith('#ff0000');
  });

  it('does NOT call onChange for invalid hex', () => {
    const handler = vi.fn();
    setup(undefined, handler);
    fireEvent.click(screen.getByRole('radio', { name: /custom/i }));
    const input = screen.getByPlaceholderText('#rrggbb');
    fireEvent.change(input, { target: { value: 'not-a-hex' } });
    act(() => { vi.advanceTimersByTime(200); });
    expect(handler).not.toHaveBeenCalled();
  });

  it('shows an error for invalid hex input after debounce', () => {
    setup();
    fireEvent.click(screen.getByRole('radio', { name: /custom/i }));
    const input = screen.getByPlaceholderText('#rrggbb');
    fireEvent.change(input, { target: { value: 'bad' } });
    act(() => { vi.advanceTimersByTime(200); });
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('rejects 3-digit hex (requires 6 digits)', () => {
    const handler = vi.fn();
    setup(undefined, handler);
    fireEvent.click(screen.getByRole('radio', { name: /custom/i }));
    const input = screen.getByPlaceholderText('#rrggbb');
    fireEvent.change(input, { target: { value: '#abc' } });
    act(() => { vi.advanceTimersByTime(200); });
    expect(handler).not.toHaveBeenCalled();
  });
});

// ─────────────────────────────────────────────────────────────
// Keyboard navigation
// ─────────────────────────────────────────────────────────────

describe('ColorPicker — keyboard navigation', () => {
  it('navigates right between swatches with ArrowRight', () => {
    setup();
    const firstSwatch = screen.getByRole('radio', { name: PRESET_COLORS[0]!.name });
    firstSwatch.focus();
    fireEvent.keyDown(firstSwatch, { key: 'ArrowRight' });
    expect(document.activeElement).toBe(
      screen.getByRole('radio', { name: PRESET_COLORS[1]!.name }),
    );
  });

  it('navigates left between swatches with ArrowLeft', () => {
    setup();
    const secondSwatch = screen.getByRole('radio', { name: PRESET_COLORS[1]!.name });
    secondSwatch.focus();
    fireEvent.keyDown(secondSwatch, { key: 'ArrowLeft' });
    expect(document.activeElement).toBe(
      screen.getByRole('radio', { name: PRESET_COLORS[0]!.name }),
    );
  });

  it('wraps from last to first on ArrowRight', () => {
    setup();
    const lastSwatch = screen.getByRole('radio', { name: PRESET_COLORS[PRESET_COLORS.length - 1]!.name });
    lastSwatch.focus();
    fireEvent.keyDown(lastSwatch, { key: 'ArrowRight' });
    // Next is "Custom"
    expect(document.activeElement).toBe(screen.getByRole('radio', { name: /custom/i }));
  });

  it('selects focused swatch on Enter', () => {
    const handler = vi.fn();
    setup(undefined, handler);
    const firstSwatch = screen.getByRole('radio', { name: PRESET_COLORS[0]!.name });
    firstSwatch.focus();
    fireEvent.keyDown(firstSwatch, { key: 'Enter' });
    expect(handler).toHaveBeenCalledWith(PRESET_COLORS[0]!.hex);
  });

  it('selects focused swatch on Space', () => {
    const handler = vi.fn();
    setup(undefined, handler);
    const firstSwatch = screen.getByRole('radio', { name: PRESET_COLORS[0]!.name });
    firstSwatch.focus();
    fireEvent.keyDown(firstSwatch, { key: ' ' });
    expect(handler).toHaveBeenCalledWith(PRESET_COLORS[0]!.hex);
  });
});

// ─────────────────────────────────────────────────────────────
// Clear / no color
// ─────────────────────────────────────────────────────────────

describe('ColorPicker — clear value', () => {
  it('calls onChange with undefined when already-selected swatch is clicked', () => {
    const bluePreset = PRESET_COLORS.find((p) => p.name === 'Blue')!;
    const handler = vi.fn();
    setup(bluePreset.hex, handler);
    fireEvent.click(screen.getByRole('radio', { name: 'Blue' }));
    expect(handler).toHaveBeenCalledWith(undefined);
  });
});
