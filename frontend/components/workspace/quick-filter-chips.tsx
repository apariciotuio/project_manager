'use client';

/**
 * EP-09 — QuickFilterChips
 * Mutually-exclusive filter chips for common mine-filter combinations.
 * Stacks with other URL params (state, type, etc.) — does not clear them.
 */
import { useRouter, useSearchParams, usePathname } from 'next/navigation';
import { useTranslations } from 'next-intl';

type MineType = 'any' | 'owner' | 'creator' | 'reviewer';

interface Chip {
  key: string;
  labelKey: string;
  mine: boolean;
  mineType?: MineType;
}

const CHIPS: Chip[] = [
  { key: 'all', labelKey: 'all', mine: false },
  { key: 'any', labelKey: 'myItems', mine: true, mineType: 'any' },
  { key: 'owner', labelKey: 'ownedByMe', mine: true, mineType: 'owner' },
  { key: 'creator', labelKey: 'createdByMe', mine: true, mineType: 'creator' },
  { key: 'reviewer', labelKey: 'pendingMyReview', mine: true, mineType: 'reviewer' },
];

function getActiveKey(mine: string | null, mineType: string | null): string {
  if (!mine || mine !== 'true') return 'all';
  return mineType ?? 'any';
}

export function QuickFilterChips() {
  const t = useTranslations('workspace.quickFilters');
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const mine = searchParams.get('mine');
  const mineType = searchParams.get('mine_type');
  const activeKey = getActiveKey(mine, mineType);

  function handleChip(chip: Chip) {
    const params = new URLSearchParams(searchParams.toString());
    const isAlreadyActive = chip.key === activeKey;

    // Deactivate: clicking active chip or "All" → remove mine params
    if (isAlreadyActive || !chip.mine) {
      params.delete('mine');
      params.delete('mine_type');
    } else {
      params.set('mine', 'true');
      params.set('mine_type', chip.mineType!);
    }

    const qs = params.toString();
    router.replace(`${pathname}${qs ? `?${qs}` : ''}`);
  }

  return (
    <div className="flex flex-wrap gap-2" role="group" aria-label={t('groupLabel')}>
      {CHIPS.map((chip) => {
        const isActive = chip.key === activeKey;
        return (
          <button
            key={chip.key}
            type="button"
            role="button"
            data-active={String(isActive)}
            aria-pressed={isActive}
            onClick={() => handleChip(chip)}
            className={[
              'rounded-full px-3 py-1 text-sm font-medium transition-colors',
              'border focus:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              isActive
                ? 'bg-primary text-primary-foreground border-primary'
                : 'bg-muted text-muted-foreground border-border hover:bg-accent',
            ].join(' ')}
          >
            {t(chip.labelKey)}
          </button>
        );
      })}
    </div>
  );
}
