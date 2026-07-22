import {randomUUID} from "node:crypto";

const CONTROL_PLANE_URL = process.env.CONTROL_PLANE_URL ?? "http://localhost:3000";
const INTERNAL_TOKEN = process.env.CONTROL_PLANE_INTERNAL_TOKEN ?? "signalchord-local-internal";

// Seeds an alert via the real internal ingestion endpoint (the same one
// alert-projector calls in production) rather than inventing a UI-only test
// fixture path — there is no UI flow that creates an alert, only the
// Kafka-driven pipeline, so this is the one legitimate way to get a real
// alert into an org for e2e purposes.
export async function seedAlert(tenantId: string, overrides: {stableId: string; title: string; suppressed?: boolean}): Promise<void> {
  const response = await fetch(`${CONTROL_PLANE_URL}/internal/v1/alerts`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-SignalChord-Internal-Token": INTERNAL_TOKEN,
    },
    body: JSON.stringify({
      tenant_id: tenantId,
      correlation_id: randomUUID(),
      event_id: randomUUID(),
      payload: {
        alert_id: overrides.stableId,
        title: overrides.title,
        summary: "Seeded by the e2e suite.",
        alert_score: 75,
        severity_code: 4,
        routing_code: 1,
        suppressed: overrides.suppressed ?? false,
        evidence_ids: ["ev-e2e-1", "ev-e2e-2"],
        graph_path_ids: [],
      },
    }),
  });
  if (!response.ok) {
    throw new Error(`seedAlert failed: ${response.status} ${await response.text()}`);
  }
}
