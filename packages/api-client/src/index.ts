export interface SessionResponse {
  access_token: string;
  token_type: "Bearer";
  expires_at: string;
  organization: {id: string; name: string; slug: string};
  user: {id: string; email: string; display_name?: string};
  role: string;
  scopes: string[];
}

export interface SourceRecord { id: string; name: string; endpoint: string; adapter: string; rights_status: string; enabled: boolean; requests_per_minute: number; raw_retention_days: number; }
export interface WatchlistItemRecord { id?: string; target_kind: string; target_stable_id: string; relevance_weight: number | string; }
export interface WatchlistRecord { id: string; name: string; description?: string; items: WatchlistItemRecord[]; }
export interface AlertRecord { id: string; stable_id: string; title: string; summary?: string; alert_score: number; severity_code: number; routing_code: number; suppressed: boolean; evidence_ids: string[]; graph_path_ids: string[]; policy_trace: Record<string, unknown>; review_status: string; relevance_feedback?: string; read_at?: string; created_at: string; }
export interface PolicyVersionRecord { id: string; version_number: number; engine: string; status: string; source_sha256?: string; ir_sha256?: string; source_size?: number; decompiled_source?: string; }
export interface PolicyRecord { id: string; name: string; description?: string; active: boolean; policy_versions?: PolicyVersionRecord[]; }
export interface InvestigationRecord { id: string; name: string; description?: string; query_template?: string; query_parameters: Record<string, unknown>; graph_layout: Record<string, unknown>; pinned_evidence_ids: string[]; }
export interface SearchHit { index: string; id: string; score: number; source: Record<string, unknown>; }
export interface EntityRecord { stable_id: string; display_name?: string; entity_type?: string; confidence?: number; status?: string; [key: string]: unknown; }
export interface GraphNode { stable_id: string; label?: string; display_name?: string; title?: string; [key: string]: unknown; }
export interface GraphRelationship { stable_id?: string; type: string; source: string; target: string; confidence?: number; [key: string]: unknown; }
export interface GraphResponse { nodes: GraphNode[]; relationships: GraphRelationship[]; truncated?: boolean; }
export interface TimelineItem { related: Record<string, unknown>; relationship_type: string; relationship: Record<string, unknown>; observed_at?: string; }
export interface NotificationEndpointRecord { id: string; platform: string; enabled: boolean; last_seen_at?: string; created_at: string; }

export class SignalChordApiError extends Error {
  constructor(public status: number, public payload: unknown) {
    super(`SignalChord API request failed with ${status}`);
  }
}

export class SignalChordClient {
  constructor(readonly baseUrl: string, private token?: string) {}
  setToken(token?: string): void { this.token = token; }
  async createSession(email: string, password: string, organizationSlug: string): Promise<SessionResponse> {
    return this.request<SessionResponse>("/api/v1/auth/session", {method: "POST", body: JSON.stringify({email, password, organization_slug: organizationSlug})}, false);
  }
  organizations() { return this.request<Array<{id: string; name: string; slug: string}>>("/api/v1/organizations"); }
  sources() { return this.request<SourceRecord[]>("/api/v1/sources"); }
  createSource(source: Partial<SourceRecord>) { return this.request<SourceRecord>("/api/v1/sources", {method: "POST", body: JSON.stringify({source})}); }
  watchlists() { return this.request<WatchlistRecord[]>("/api/v1/watchlists"); }
  createWatchlist(watchlist: {name: string; description?: string; items: WatchlistItemRecord[]}) { return this.request<WatchlistRecord>("/api/v1/watchlists", {method: "POST", body: JSON.stringify({watchlist})}); }
  alerts(unread = false) { return this.request<AlertRecord[]>(`/api/v1/alerts${unread ? "?unread=true" : ""}`); }
  updateAlert(id: string, alert: Partial<AlertRecord>) { return this.request<AlertRecord>(`/api/v1/alerts/${encodeURIComponent(id)}`, {method: "PATCH", body: JSON.stringify({alert})}); }
  policies() { return this.request<PolicyRecord[]>("/api/v1/policies"); }
  simulatePolicy(id: string, inputs: Record<string, number>) { return this.request<Record<string, unknown>>(`/api/v1/policies/${encodeURIComponent(id)}/simulate`, {method: "POST", body: JSON.stringify({inputs})}); }
  uploadPolicy(id: string, midiBase64: string) { return this.request<PolicyVersionRecord>(`/api/v1/policies/${encodeURIComponent(id)}/upload_velato`, {method: "POST", body: JSON.stringify({midi_base64: midiBase64})}); }
  investigations() { return this.request<InvestigationRecord[]>("/api/v1/investigations"); }
  createInvestigation(investigation: Partial<InvestigationRecord>) { return this.request<InvestigationRecord>("/api/v1/investigations", {method: "POST", body: JSON.stringify({investigation})}); }
  search(query: string) { return this.request<{query: string; results: SearchHit[]}>(`/api/v1/search?q=${encodeURIComponent(query)}`); }
  entity(stableId: string) { return this.request<EntityRecord>(`/api/v1/entities/${encodeURIComponent(stableId)}`); }
  entityTimeline(stableId: string) { return this.request<{items: TimelineItem[]}>(`/api/v1/entities/${encodeURIComponent(stableId)}/timeline`); }
  entityGraph(stableId: string) { return this.request<GraphResponse>(`/api/v1/entities/${encodeURIComponent(stableId)}/graph`); }
  notificationEndpoints() { return this.request<NotificationEndpointRecord[]>("/api/v1/notification_endpoints"); }
  registerNotificationEndpoint(platform: string, token: string) { return this.request<NotificationEndpointRecord>("/api/v1/notification_endpoints", {method: "POST", body: JSON.stringify({platform, token})}); }
  removeNotificationEndpoint(id: string) { return this.request<null>(`/api/v1/notification_endpoints/${encodeURIComponent(id)}`, {method: "DELETE"}); }

  private async request<T>(path: string, init: RequestInit = {}, authenticated = true): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    if (init.body) headers.set("Content-Type", "application/json");
    if (authenticated && this.token) headers.set("Authorization", `Bearer ${this.token}`);
    const response = await fetch(`${this.baseUrl}${path}`, {...init, headers});
    const text = await response.text();
    const payload = text ? JSON.parse(text) : null;
    if (!response.ok) throw new SignalChordApiError(response.status, payload);
    return payload as T;
  }
}
