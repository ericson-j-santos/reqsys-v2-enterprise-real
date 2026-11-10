export type ApprovedSource = Readonly<{ repository: string; issue: number; label: string }>;
export type IssueReadback = Readonly<{
  state: 'open' | 'closed';
  title: string;
  updated: string;
  checked: string;
}>;
export const APPROVED_SOURCES: readonly ApprovedSource[];
export function sourceLink(target: ApprovedSource): string;
export function readPublicIssue(
  target: ApprovedSource,
  fetcher: typeof fetch,
  signal: AbortSignal,
  clock?: () => string
): Promise<IssueReadback>;
