/**
 * Minimal toast utility for error notifications.
 * Renders a dismissible toast div into document.body.
 * Auto-dismisses after 6 seconds per spec.
 *
 * No external dependencies — avoids adding shadcn/Toaster setup.
 */

const TOAST_DURATION_MS = 6000;

export function showErrorToast(code: string, message: string): void {
  if (typeof document === 'undefined') return; // SSR guard

  // Deduplicate by (code, message) within the display window
  const dedupeKey = `toast-${code}-${message}`;
  if (document.getElementById(dedupeKey)) return;

  const container = getOrCreateContainer();

  const toast = document.createElement('div');
  toast.id = dedupeKey;
  toast.role = 'alert';
  toast.setAttribute('aria-live', 'assertive');
  toast.style.cssText = [
    'display:flex',
    'align-items:flex-start',
    'gap:8px',
    'background:hsl(var(--destructive,0 84% 60%))',
    'color:hsl(var(--destructive-foreground,0 0% 98%))',
    'padding:12px 16px',
    'border-radius:6px',
    'font-size:0.875rem',
    'line-height:1.4',
    'box-shadow:0 4px 12px rgba(0,0,0,.15)',
    'max-width:360px',
    'pointer-events:auto',
  ].join(';');

  const text = document.createElement('span');
  text.style.flex = '1';
  text.textContent = `${code}: ${message}`;

  const close = document.createElement('button');
  close.type = 'button';
  close.setAttribute('aria-label', 'Dismiss');
  close.style.cssText = 'background:none;border:none;cursor:pointer;color:inherit;opacity:.7;padding:0;font-size:1rem;line-height:1';
  close.textContent = '×';
  close.addEventListener('click', () => remove());

  toast.appendChild(text);
  toast.appendChild(close);
  container.appendChild(toast);

  const timer = setTimeout(() => remove(), TOAST_DURATION_MS);

  function remove() {
    clearTimeout(timer);
    toast.remove();
    if (container.childElementCount === 0) container.remove();
  }
}

function getOrCreateContainer(): HTMLElement {
  const id = 'error-toast-container';
  let el = document.getElementById(id);
  if (!el) {
    el = document.createElement('div');
    el.id = id;
    el.style.cssText = [
      'position:fixed',
      'bottom:16px',
      'right:16px',
      'z-index:9999',
      'display:flex',
      'flex-direction:column',
      'gap:8px',
      'pointer-events:none',
    ].join(';');
    document.body.appendChild(el);
  }
  return el;
}
