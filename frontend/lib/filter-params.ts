/**
 * EP-14 — URL filter parameter key constants.
 * Centralises all URL query-param keys to prevent drift between
 * the filter panel and the API call.
 */

/** Query param key used to filter work items to descendants of a given ancestor. */
export const ANCESTOR_ID_PARAM = 'ancestor_id' as const;
