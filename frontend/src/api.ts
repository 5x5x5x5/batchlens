import { createApiClient, query, type HelpEntry, type HelpPage } from "@plantcraft/ui";
import { href } from "./nav";
import type { BatchDetail, BatchList, Me, Metrics, Samples, Trends } from "./types";

const client = createApiClient({ app: "batchlens", href });
export const UNAUTHORIZED_EVENT = client.UNAUTHORIZED_EVENT;
const request = client.request;
const id = encodeURIComponent;

export const api = {
  me: () => request<Me>("/api/me"),
  batches: () => request<BatchList>("/api/batches"),
  batch: (batchId: string, asOf?: string) => request<BatchDetail>(`/api/batches/${id(batchId)}${query({ as_of: asOf })}`),
  /** `asOf`: only what had been collected and reported by that instant. `alignTo`: another
   * batch, to lay this one's samples over it at the same culture age. */
  samples: (batchId: string, asOf?: string, alignTo?: string) => request<Samples>(`/api/batches/${id(batchId)}/samples${query({ as_of: asOf, align_to: alignTo })}`),
  metrics: (batchId: string, asOf?: string) => request<Metrics>(`/api/batches/${id(batchId)}/metrics${query({ as_of: asOf })}`),
  trends: (batchId: string, asOf?: string) => request<Trends>(`/api/batches/${id(batchId)}/trends${query({ as_of: asOf })}`),
  help: () => request<HelpEntry[]>("/api/help"),
  helpPage: (pageId: string) => request<HelpPage>(`/api/help/${id(pageId)}`),
};
