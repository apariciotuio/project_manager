'use client';

/**
 * EP-11 — Jira Export Button
 *
 * Renders an "Export to Jira" button gated on `canExport`.
 * On 202: shows success toast + disables for 30 s (optimistic lockout).
 * On 4xx/5xx: shows error toast.
 * If `externalJiraKey` is set, renders a link to the Jira issue.
 */

import { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { exportToJira } from '@/lib/api/work-items';
import { ApiError, UnauthenticatedError } from '@/lib/api-client';
import { showErrorToast } from '@/lib/errors/toast';

const LOCKOUT_MS = 30_000;

interface JiraExportButtonProps {
  workItemId: string;
  canExport: boolean;
  /** e.g. "ABC-123" — null hides the link */
  externalJiraKey: string | null;
  /** Base URL for Jira links — defaults to empty string (relative), consumers should supply real base */
  jiraBaseUrl?: string;
}

export function JiraExportButton({
  workItemId,
  canExport,
  externalJiraKey,
  jiraBaseUrl = '',
}: JiraExportButtonProps) {
  const [lockedOut, setLockedOut] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const lockoutTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (lockoutTimer.current) clearTimeout(lockoutTimer.current);
    };
  }, []);

  if (!canExport) return null;

  async function handleExport() {
    if (lockedOut || exporting) return;
    setExporting(true);
    setSuccessMessage(null);
    try {
      await exportToJira(workItemId);
      setSuccessMessage('Export queued');
      setLockedOut(true);
      lockoutTimer.current = setTimeout(() => setLockedOut(false), LOCKOUT_MS);
    } catch (err) {
      if (err instanceof UnauthenticatedError) {
        showErrorToast('EXPORT_FORBIDDEN', 'Not authorised to export');
      } else if (err instanceof ApiError) {
        if (err.status >= 500) {
          showErrorToast('EXPORT_ERROR', 'Export failed — please retry');
        } else if (err.status === 401 || err.status === 403) {
          showErrorToast('EXPORT_FORBIDDEN', err.message ?? 'Not authorised to export');
        } else {
          showErrorToast(err.code ?? 'EXPORT_ERROR', err.message ?? 'Export failed');
        }
      } else {
        showErrorToast('EXPORT_ERROR', 'Unexpected error — please retry');
      }
    } finally {
      setExporting(false);
    }
  }

  const jiraLink = externalJiraKey ? (
    <a
      href={`${jiraBaseUrl}/browse/${externalJiraKey}`}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={`Open Jira issue ${externalJiraKey}`}
      data-testid="jira-issue-link"
      className="inline-flex items-center gap-1 rounded-md border border-border bg-background px-2 py-0.5 text-xs font-medium text-primary hover:underline"
    >
      Jira: {externalJiraKey}
    </a>
  ) : null;

  return (
    <div className="flex items-center gap-2" data-testid="jira-export-wrapper">
      {jiraLink}
      <Button
        size="sm"
        variant="outline"
        disabled={lockedOut || exporting}
        aria-label="Export to Jira"
        aria-busy={exporting}
        data-testid="jira-export-button"
        onClick={() => void handleExport()}
        className="w-full sm:w-auto"
      >
        {exporting ? 'Exporting...' : lockedOut ? 'Export queued' : 'Export to Jira'}
      </Button>
      {successMessage && (
        <span
          role="status"
          aria-live="polite"
          data-testid="jira-export-success"
          className="text-xs text-muted-foreground"
        >
          {successMessage}
        </span>
      )}
    </div>
  );
}
