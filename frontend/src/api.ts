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
  batch: (batchId: string) => request<BatchDetail>(`/api/batches/${id(batchId)}`),
  /** `alignTo`: another batch, to lay this one's samples over it at the same culture age. */
  samples: (batchId: string, alignTo?: string) => request<Samples>(`/api/batches/${id(batchId)}/samples${query({ align_to: alignTo })}`),
  metrics: (batchId: string) => request<Metrics>(`/api/batches/${id(batchId)}/metrics`),
  trends: (batchId: string) => request<Trends>(`/api/batches/${id(batchId)}/trends`),
  help: () => request<HelpEntry[]>("/api/help"),
  helpPage: (pageId: string) => request<HelpPage>(`/api/help/${id(pageId)}`),
};
