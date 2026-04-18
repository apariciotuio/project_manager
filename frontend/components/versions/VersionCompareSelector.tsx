'use client';

import { useTranslations } from 'next-intl';
import type { WorkItemVersion } from '@/lib/types/versions';

interface VersionCompareSelectorProps {
  workItemId: string;
  versions: WorkItemVersion[];
  fromVersion: number;
  toVersion: number;
  onChange: (from: number, to: number) => void;
}

export function VersionCompareSelector({
  versions,
  fromVersion,
  toVersion,
  onChange,
}: VersionCompareSelectorProps) {
  const t = useTranslations('workspace.itemDetail.versions');

  const isInvalid = fromVersion >= toVersion;

  function handleFromChange(e: React.ChangeEvent<HTMLSelectElement>) {
    onChange(Number(e.target.value), toVersion);
  }

  function handleToChange(e: React.ChangeEvent<HTMLSelectElement>) {
    onChange(fromVersion, Number(e.target.value));
  }

  function handleSwap() {
    onChange(toVersion, fromVersion);
  }

  return (
    <div className="flex items-center gap-3 flex-wrap">
      {/* From selector */}
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">{t('fromVersion')}</label>
        <select
          aria-label={t('fromVersion')}
          value={fromVersion}
          onChange={handleFromChange}
          className="rounded border border-input bg-background px-2 py-1 text-sm"
        >
          {versions.map((v) => (
            <option key={v.version_number} value={v.version_number}>
              v{v.version_number}
              {v.commit_message ? ` — ${v.commit_message}` : ''}
            </option>
          ))}
        </select>
      </div>

      {/* Swap button */}
      <button
        type="button"
        aria-label="Swap from and to versions"
        onClick={handleSwap}
        className="mt-4 rounded border border-input bg-background px-2 py-1 text-sm hover:bg-muted"
      >
        ⇄
      </button>

      {/* To selector */}
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">{t('toVersion')}</label>
        <select
          aria-label={t('toVersion')}
          value={toVersion}
          onChange={handleToChange}
          className="rounded border border-input bg-background px-2 py-1 text-sm"
        >
          {versions.map((v) => (
            <option key={v.version_number} value={v.version_number}>
              v{v.version_number}
              {v.commit_message ? ` — ${v.commit_message}` : ''}
            </option>
          ))}
        </select>
      </div>

      {/* Inline validation error */}
      {isInvalid && (
        <p role="alert" className="w-full text-xs text-destructive">
          {t('invalidDiffRange')}
        </p>
      )}
    </div>
  );
}
