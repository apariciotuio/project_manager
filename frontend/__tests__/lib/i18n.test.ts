import { describe, it, expect } from 'vitest';
import { t, icuLite, es } from '@/lib/i18n';

describe('t() typed getter', () => {
  it('resolves top-level namespace key', () => {
    expect(t('common.app.title')).toBe('Work Maturation Platform');
  });

  it('resolves nested key', () => {
    expect(t('workitem.state.draft')).toBe('Borrador');
  });

  it('resolves state colors', () => {
    expect(t('workitem.state.ready')).toBe('Listo');
    expect(t('workitem.state.blocked')).toBe('Bloqueado');
  });

  it('resolves error key', () => {
    expect(t('errors.generic')).toBe('Algo salió mal. Inténtalo de nuevo.');
  });

  it('resolves deep auth error', () => {
    expect(t('errors.auth.no_workspace')).toBe(
      'Tu cuenta no tiene acceso a ningún workspace.'
    );
  });

  it('resolves mcp field', () => {
    expect(t('mcp.status.active')).toBe('Activa');
  });

  it('resolves role name', () => {
    expect(t('role.names.techLead')).toBe('Tech Lead');
  });
});

describe('icuLite()', () => {
  it('interpolates simple variable', () => {
    expect(icuLite('Hola {name}', { name: 'Ana' })).toBe('Hola Ana');
  });

  it('handles missing variable with fallback', () => {
    expect(icuLite('Hola {name}', {})).toBe('Hola {name}');
  });

  it('handles plural one', () => {
    expect(icuLite('{count, plural, one{1 elemento} other{{count} elementos}}', { count: 1 })).toBe(
      '1 elemento'
    );
  });

  it('handles plural other', () => {
    expect(icuLite('{count, plural, one{1 elemento} other{{count} elementos}}', { count: 5 })).toBe(
      '5 elementos'
    );
  });

  it('handles select', () => {
    expect(icuLite('{role, select, admin{Admin} other{Usuario}}', { role: 'admin' })).toBe('Admin');
    expect(icuLite('{role, select, admin{Admin} other{Usuario}}', { role: 'viewer' })).toBe(
      'Usuario'
    );
  });

  it('handles multiple variables', () => {
    expect(icuLite('{name} tiene {count} elementos', { name: 'Ana', count: 3 })).toBe(
      'Ana tiene 3 elementos'
    );
  });
});

describe('es dictionary structure', () => {
  it('has all required namespaces', () => {
    expect(es).toHaveProperty('common');
    expect(es).toHaveProperty('errors');
    expect(es).toHaveProperty('workitem');
    expect(es).toHaveProperty('review');
    expect(es).toHaveProperty('hierarchy');
    expect(es).toHaveProperty('tags');
    expect(es).toHaveProperty('attachment');
    expect(es).toHaveProperty('lock');
    expect(es).toHaveProperty('mcp');
    expect(es).toHaveProperty('assistant');
    expect(es).toHaveProperty('role');
  });
});
