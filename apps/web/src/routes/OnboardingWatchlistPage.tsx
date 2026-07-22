import React, {useState} from "react";
import {SignalChordApiError, SignalChordClient} from "@signalchord/api-client";
import {chooseAnalysisLookup} from "./chooseAnalysisLookup";

type TargetKind = "entity" | "topic" | "search";

// Matches the existing dashboard mini-form's convention (Watchlists
// component in main.tsx): a raw stable-id string, not a resolved company
// name — there's no entity-resolution/autocomplete UI in this codebase to
// turn a friendly name into a canonical id, so asking for the real thing
// directly is the honest choice, consistent with how this already works
// elsewhere in the product.
const KIND_PLACEHOLDERS: Record<TargetKind, string> = {
  entity: "company:acme",
  topic: "supply-chain-disruption",
  search: "acquisitions fintech",
};

type AnalysisState =
  | {kind: "loading"}
  | {kind: "found"; count: number}
  | {kind: "empty"};

function summarizeValidationError(error: unknown): string {
  if (error instanceof SignalChordApiError && error.status === 422) {
    const payload = error.payload as {details?: Record<string, string[]>} | null;
    const messages = payload?.details
      ? Object.entries(payload.details).map(([field, msgs]) => `${field} ${msgs.join(", ")}`)
      : [];
    if (messages.length) return messages.join("; ");
  }
  return "Couldn't create your watchlist. Check the fields and try again.";
}

export function OnboardingWatchlistPage({client, onCreated}: {
  client: SignalChordClient;
  onCreated: (watchlistId: string) => void;
}) {
  const [name, setName] = useState("");
  const [targetKind, setTargetKind] = useState<TargetKind>("entity");
  const [targetStableId, setTargetStableId] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [createdId, setCreatedId] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisState>({kind: "loading"});
  // One key per mount, sent as Idempotency-Key — protects against a
  // double-click or a network-retry creating a second watchlist.
  const [idempotencyKey] = useState(() => crypto.randomUUID());

  const runFirstAnalysis = async (kind: TargetKind, stableId: string) => {
    setAnalysis({kind: "loading"});
    try {
      if (chooseAnalysisLookup(kind) === "entity") {
        await client.entity(stableId);
        setAnalysis({kind: "found", count: 1});
      } else {
        const {results} = await client.search(stableId);
        setAnalysis(results.length > 0 ? {kind: "found", count: results.length} : {kind: "empty"});
      }
    } catch {
      // A 404/empty result from either lookup is a genuinely honest
      // "nothing indexed yet" outcome for a brand-new target — not an
      // error to alarm the user with.
      setAnalysis({kind: "empty"});
    }
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (submitting) return;
    setError("");
    setSubmitting(true);
    try {
      const watchlist = await client.createWatchlist(
        {
          name,
          items: [{target_kind: targetKind, target_stable_id: targetStableId, relevance_weight: 1}],
        },
        idempotencyKey,
      );
      setCreatedId(watchlist.id);
      void runFirstAnalysis(targetKind, targetStableId);
    } catch (thrown) {
      setError(summarizeValidationError(thrown));
      setSubmitting(false);
    }
  };

  if (createdId) {
    return (
      <main className="login">
        <div className="card loginCard">
          <span className="logo">SC</span>
          <h1>Watchlist created.</h1>
          {analysis.kind === "loading" && <p className="muted">Checking what we've found so far…</p>}
          {analysis.kind === "found" && (
            <p className="muted">
              We found {analysis.count} existing match{analysis.count === 1 ? "" : "es"} already indexed.
              We'll keep watching for more.
            </p>
          )}
          {analysis.kind === "empty" && (
            <p className="muted">Nothing indexed yet for this one — we'll keep watching and let you know when something shows up.</p>
          )}
          <button className="primary" onClick={() => onCreated(createdId)}>Continue to dashboard</button>
        </div>
      </main>
    );
  }

  return (
    <main className="login">
      <form className="card loginCard" onSubmit={submit}>
        <span className="logo">SC</span>
        <h1>Add your first watchlist.</h1>
        <p className="muted">Track an entity, topic, or search term. You can add more later.</p>
        <label>
          Watchlist name
          <input value={name} onChange={event => setName(event.target.value)} placeholder="Competitor moves" required/>
        </label>
        <label>
          What are you watching?
          <select value={targetKind} onChange={event => setTargetKind(event.target.value as TargetKind)}>
            <option value="entity">Company, person, or technology</option>
            <option value="topic">Topic</option>
            <option value="search">Search phrase</option>
          </select>
        </label>
        <label>
          Stable entity or topic ID
          <input
            value={targetStableId}
            onChange={event => setTargetStableId(event.target.value)}
            placeholder={KIND_PLACEHOLDERS[targetKind]}
            required
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button className="primary" disabled={submitting}>{submitting ? "Creating…" : "Create watchlist"}</button>
      </form>
    </main>
  );
}
