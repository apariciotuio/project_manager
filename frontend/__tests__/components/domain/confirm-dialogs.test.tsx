import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { TypedConfirmDialog } from '@/components/domain/typed-confirm-dialog';
import { CheckboxConfirmDialog } from '@/components/domain/checkbox-confirm-dialog';

describe('TypedConfirmDialog', () => {
  it('renders trigger', () => {
    render(
      <TypedConfirmDialog
        title="Eliminar workspace"
        description="Esta acción no se puede deshacer."
        expected="produccion"
        onConfirm={() => {}}
        trigger={<button>Eliminar</button>}
      />
    );
    expect(screen.getByText('Eliminar')).toBeTruthy();
  });

  it('opens dialog on trigger click', () => {
    render(
      <TypedConfirmDialog
        title="Eliminar workspace"
        description="Esta acción no se puede deshacer."
        expected="produccion"
        onConfirm={() => {}}
        trigger={<button>Abrir</button>}
      />
    );
    fireEvent.click(screen.getByText('Abrir'));
    expect(screen.getByText('Eliminar workspace')).toBeTruthy();
  });

  it('confirm button disabled initially', () => {
    render(
      <TypedConfirmDialog
        title="Eliminar"
        description="Descripción"
        expected="produccion"
        onConfirm={() => {}}
        trigger={<button>Abrir</button>}
      />
    );
    fireEvent.click(screen.getByText('Abrir'));
    const confirmBtn = screen.getByRole('button', { name: /Confirmar/i });
    expect(confirmBtn.hasAttribute('disabled')).toBe(true);
  });

  it('confirm button enabled when expected text typed', () => {
    render(
      <TypedConfirmDialog
        title="Eliminar"
        description="Descripción"
        expected="produccion"
        onConfirm={() => {}}
        trigger={<button>Abrir</button>}
      />
    );
    fireEvent.click(screen.getByText('Abrir'));
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'produccion' } });
    const confirmBtn = screen.getByRole('button', { name: /Confirmar/i });
    expect(confirmBtn.hasAttribute('disabled')).toBe(false);
  });

  it('calls onConfirm when confirmed', () => {
    const onConfirm = vi.fn();
    render(
      <TypedConfirmDialog
        title="Eliminar"
        description="Descripción"
        expected="produccion"
        onConfirm={onConfirm}
        trigger={<button>Abrir</button>}
      />
    );
    fireEvent.click(screen.getByText('Abrir'));
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'produccion' } });
    fireEvent.click(screen.getByRole('button', { name: /Confirmar/i }));
    expect(onConfirm).toHaveBeenCalledOnce();
  });
});

describe('CheckboxConfirmDialog', () => {
  it('renders trigger', () => {
    render(
      <CheckboxConfirmDialog
        title="Forzar aprobación"
        description="Esta acción queda registrada."
        checkboxLabel="Entiendo que esta acción no se puede deshacer"
        onConfirm={() => {}}
        trigger={<button>Forzar</button>}
      />
    );
    expect(screen.getByText('Forzar')).toBeTruthy();
  });

  it('confirm disabled until checkbox checked', () => {
    render(
      <CheckboxConfirmDialog
        title="Forzar"
        description="Descripción"
        checkboxLabel="Entiendo"
        onConfirm={() => {}}
        trigger={<button>Abrir</button>}
      />
    );
    fireEvent.click(screen.getByText('Abrir'));
    const confirmBtn = screen.getByRole('button', { name: /Confirmar/i });
    expect(confirmBtn.hasAttribute('disabled')).toBe(true);
  });

  it('confirm enabled when checkbox checked', () => {
    render(
      <CheckboxConfirmDialog
        title="Forzar"
        description="Descripción"
        checkboxLabel="Entiendo"
        onConfirm={() => {}}
        trigger={<button>Abrir</button>}
      />
    );
    fireEvent.click(screen.getByText('Abrir'));
    const checkbox = screen.getByRole('checkbox');
    fireEvent.click(checkbox);
    const confirmBtn = screen.getByRole('button', { name: /Confirmar/i });
    expect(confirmBtn.hasAttribute('disabled')).toBe(false);
  });
});
