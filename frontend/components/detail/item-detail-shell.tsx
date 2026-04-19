'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslations } from 'next-intl';
import { Pencil } from 'lucide-react';
import { ChatPanel } from '@/components/clarification/chat-panel';
import { CommentsTab } from '@/components/work-item/comments-tab';
import { ReviewsTab } from '@/components/work-item/reviews-tab';
import { TimelineTab } from '@/components/work-item/timeline-tab';
import { AttachmentList } from '@/components/attachments/attachment-list';
import { AttachmentDropZone } from '@/components/attachments/attachment-drop-zone';
import { CompletenessPanel } from '@/components/work-item/completeness-panel';
import { VersionHistoryPanel } from '@/components/work-item/version-history-panel';
import { SpecificationSectionsEditor } from '@/components/work-item/specification-sections-editor';
import { ChildItemsTab } from '@/components/work-item/child-items-tab';
import { WorkItemEditModal } from '@/components/work-item/work-item-edit-modal';
import { LockBadge } from '@/components/domain/lock-badge';
import { Button } from '@/components/ui/button';
import { SplitViewContext } from './split-view-context';
import type { PendingSuggestion } from './split-view-context';
import type { WorkItemResponse } from '@/lib/types/work-item';

export type TabId =
  | 'chat'
  | 'template'
  | 'comments'
  | 'reviews'
  | 'timeline'
  | 'adjuntos'
  | 'completeness'
  | 'diff'
  | 'dependencies'
  | 'history';

const KNOWN_ITEM_TYPES = ['story', 'epic', 'milestone', 'task', 'bug'] as const;
const DESKTOP_MIN_WIDTH_PX = 1024;
const NO_TEMPLATE_NOTICE = 'No template — using generic view.';

export interface ItemDetailShellProps {
  workItem: WorkItemResponse;
  slug: string;
  canEdit: boolean;
  latestVersionId: string | null;
}

export function ItemDetailShell({
  workItem,
  slug,
  canEdit,
  latestVersionId,
}: ItemDetailShellProps) {
  const t = useTranslations('workspace.itemDetail.shell');
  const [activeTab, setActiveTab] = useState<TabId>('template');
  const [isMobile, setIsMobile] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [highlightedSectionId, setHighlightedSectionId] = useState<string | null>(null);
  const [pendingSuggestions, setPendingSuggestions] = useState<
    Record<string, PendingSuggestion>
  >({});

  useEffect(() => {
    function check() {
      setIsMobile(window.innerWidth < DESKTOP_MIN_WIDTH_PX);
    }
    check();
    window.addEventListener('resize', check);
    return () => window.removeEventListener('resize', check);
  }, []);

  const emitSuggestion = useCallback((sug: PendingSuggestion) => {
    setPendingSuggestions((prev) => ({ ...prev, [sug.section_type]: sug }));
  }, []);
  const clearSuggestion = useCallback((section_type: string) => {
    setPendingSuggestions((prev) => {
      const next = { ...prev };
      delete next[section_type];
      return next;
    });
  }, []);

  const contextValue = {
    highlightedSectionId,
    setHighlightedSectionId,
    pendingSuggestions,
    emitSuggestion,
    clearSuggestion,
  };

  const tabs = useMemo<Array<{ id: TabId; label: string; mobileOnly?: boolean }>>(() => {
    const base: Array<{ id: TabId; label: string; mobileOnly?: boolean }> = [];
    if (isMobile) {
      base.push({ id: 'chat', label: 'Chat', mobileOnly: true });
    }
    base.push(
      { id: 'template', label: t('tabs.template') },
      { id: 'comments', label: t('tabs.comments') },
      { id: 'reviews', label: t('tabs.reviews') },
      { id: 'timeline', label: t('tabs.timeline') },
      { id: 'adjuntos', label: t('tabs.adjuntos') },
      { id: 'completeness', label: t('tabs.completeness') },
      { id: 'diff', label: t('tabs.diff') },
      { id: 'dependencies', label: t('tabs.dependencies') },
      { id: 'history', label: t('tabs.history') },
    );
    return base;
  }, [isMobile, t]);

  const hasTemplate =
    typeof workItem.type === 'string' &&
    workItem.type.length > 0 &&
    (KNOWN_ITEM_TYPES as readonly string[]).includes(workItem.type);

  const tabRefs = useRef<Map<TabId, HTMLButtonElement | null>>(new Map());

  function handleTablistKeyDown(e: React.KeyboardEvent<HTMLDivElement>) {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
    const current = document.activeElement as HTMLElement | null;
    const idx = tabs.findIndex((tab) => tabRefs.current.get(tab.id) === current);
    if (idx === -1) return;
    e.preventDefault();
    const dir = e.key === 'ArrowRight' ? 1 : -1;
    const nextIdx = (idx + dir + tabs.length) % tabs.length;
    const nextTabId = tabs[nextIdx]!.id;
    tabRefs.current.get(nextTabId)?.focus();
  }

  function renderPanelContent(tabId: TabId) {
    switch (tabId) {
      case 'chat':
        return null; // chat column is rendered separately; this panel is a placeholder
      case 'template':
        if (!hasTemplate) {
          return (
            <div className="p-4 text-sm text-muted-foreground">
              <p>{NO_TEMPLATE_NOTICE}</p>
              <p className="mt-2 whitespace-pre-wrap">{workItem.description ?? ''}</p>
            </div>
          );
        }
        return (
          <div className="p-4">
            <SpecificationSectionsEditor workItemId={workItem.id} canEdit={canEdit} />
          </div>
        );
      case 'comments':
        return (
          <div className="p-4">
            <CommentsTab workItemId={workItem.id} />
          </div>
        );
      case 'reviews':
        return (
          <div className="p-4">
            <ReviewsTab workItemId={workItem.id} versionId={latestVersionId} />
          </div>
        );
      case 'timeline':
        return (
          <div className="p-4">
            <TimelineTab workItemId={workItem.id} />
          </div>
        );
      case 'adjuntos':
        return (
          <div className="p-4 flex flex-col gap-4">
            <AttachmentDropZone disabled={!canEdit} />
            <AttachmentList
              workItemId={workItem.id}
              canEdit={canEdit}
              currentUserId={workItem.owner_id ?? ''}
              isSuperadmin={false}
            />
          </div>
        );
      case 'completeness':
        return (
          <div className="p-4">
            <CompletenessPanel workItemId={workItem.id} />
          </div>
        );
      case 'diff':
        return (
          <div className="p-4 text-sm text-muted-foreground">
            Select a version from the History tab to compare.
          </div>
        );
      case 'dependencies':
        return (
          <div className="p-4">
            <ChildItemsTab workItemId={workItem.id} slug={slug} />
          </div>
        );
      case 'history':
        return (
          <div className="p-4">
            <VersionHistoryPanel workItemId={workItem.id} />
          </div>
        );
    }
  }

  const showChatColumn = !isMobile || activeTab === 'chat';
  const showTemplateColumn = !isMobile || activeTab !== 'chat';

  return (
    <SplitViewContext.Provider value={contextValue}>
      <div className="flex flex-col h-full min-h-0" data-testid="item-detail-shell">
        {canEdit && (
          <WorkItemEditModal
            open={editOpen}
            workItem={workItem}
            onClose={() => setEditOpen(false)}
            onSaved={() => setEditOpen(false)}
          />
        )}

        <div className="flex items-center gap-2 border-b border-border px-4 py-2 bg-background">
          <div
            role="tablist"
            aria-label={t('tablistLabel')}
            className="flex gap-1 overflow-x-auto flex-1"
            onKeyDown={handleTablistKeyDown}
          >
            {tabs.map((tab) => {
              const selected = tab.id === activeTab;
              return (
                <button
                  key={tab.id}
                  ref={(el) => {
                    tabRefs.current.set(tab.id, el);
                  }}
                  id={`tab-${tab.id}`}
                  role="tab"
                  type="button"
                  aria-selected={selected}
                  aria-controls={`panel-${tab.id}`}
                  tabIndex={selected ? 0 : -1}
                  onClick={() => setActiveTab(tab.id)}
                  className={`px-3 py-1.5 text-sm rounded-md whitespace-nowrap focus:outline-none focus-visible:ring-2 ${
                    selected
                      ? 'bg-primary/10 text-primary font-medium'
                      : 'text-muted-foreground hover:bg-muted'
                  }`}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <LockBadge locked={false} />
            {canEdit && (
              <Button
                size="sm"
                variant="outline"
                aria-label={t('editAria')}
                onClick={() => setEditOpen(true)}
              >
                <Pencil className="h-4 w-4 mr-1.5" />
                {t('edit')}
              </Button>
            )}
          </div>
        </div>

        <div className="flex flex-1 min-h-0">
          <div
            className="flex flex-col min-h-0 overflow-hidden border-r border-border"
            style={{
              width: isMobile ? '100%' : '40%',
              display: showChatColumn ? undefined : 'none',
            }}
          >
            <ChatPanel workItemId={workItem.id} />
          </div>

          <div
            className="flex-1 min-h-0 overflow-auto"
            style={{ display: showTemplateColumn ? undefined : 'none' }}
          >
            <div className="px-4 pt-3">
              <h1 className="text-xl font-semibold">{workItem.title}</h1>
            </div>
            {tabs.map((tab) => {
              if (tab.id === 'chat') {
                return (
                  <div
                    key="panel-chat"
                    id="panel-chat"
                    role="tabpanel"
                    aria-labelledby="tab-chat"
                    hidden
                  />
                );
              }
              const active = tab.id === activeTab;
              return (
                <div
                  key={`panel-${tab.id}`}
                  id={`panel-${tab.id}`}
                  role="tabpanel"
                  aria-labelledby={`tab-${tab.id}`}
                  hidden={!active}
                >
                  {active ? renderPanelContent(tab.id) : null}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </SplitViewContext.Provider>
  );
}
