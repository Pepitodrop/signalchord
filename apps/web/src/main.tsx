import React, {useCallback, useEffect, useMemo, useRef, useState} from "react";
import {createRoot} from "react-dom/client";
import cytoscape from "cytoscape";
import {
  AlertRecord,
  MeResponse,
  PolicyRecord,
  SignalChordClient,
  SourceRecord,
  WatchlistRecord,
} from "@signalchord/api-client";
import {VelatoShowcase} from "./VelatoShowcase";
import {SignupPage} from "./routes/SignupPage";
import {VerifyEmailPage} from "./routes/VerifyEmailPage";
import {LoginPage} from "./routes/LoginPage";
import {OnboardingWorkspacePage} from "./routes/OnboardingWorkspacePage";
import {OnboardingWatchlistPage} from "./routes/OnboardingWatchlistPage";
import {stepForMe, type Step} from "./routes/deriveStep";
import {describeEvidenceCount, EVIDENCE_DISCLOSURE_LABEL} from "./routes/describeEvidence";
import {describePolicy} from "./routes/describePolicy";
import "./styles.css";

type View = "overview" | "entities" | "alerts" | "watchlists" | "sources" | "policies";
const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:3000";
const REALTIME_URL = import.meta.env.VITE_REALTIME_URL ?? "http://localhost:8088";

function useAlerts(client: SignalChordClient, token: string) {
  const [alerts, setAlerts] = useState<AlertRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [live, setLive] = useState(false);
  const load = useCallback(() => client.alerts().then(records => {
    setAlerts(records);
    setLoading(false);
  }), [client]);

  useEffect(() => {
    void load();
  }, [load]);

  // 30s polling floor for feed freshness — independent of the SSE trigger
  // below, which degrades gracefully to "Offline" today (no cookie-auth
  // support in realtime-gateway) and shouldn't be the only way the feed
  // ever updates.
  useEffect(() => {
    const id = setInterval(() => void load(), 30_000);
    return () => clearInterval(id);
  }, [load]);

  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      try {
        const response = await fetch(`${REALTIME_URL}/events`, {
          headers: {Authorization: `Bearer ${token}`},
          signal: controller.signal,
        });
        if (!response.ok || !response.body) return;
        setLive(true);
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (!controller.signal.aborted) {
          const {done, value} = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, {stream: true});
          const frames = buffer.split("\n\n");
          buffer = frames.pop() ?? "";
          if (frames.some(frame => frame.includes("event: alert"))) void load();
        }
      } catch {
        setLive(false);
      }
    })();
    return () => controller.abort();
  }, [load, token]);

  return {alerts, loading, live, reload: load};
}

function Graph({
  nodes,
  edges,
}: {
  nodes: Array<{id: string; label: string}>;
  edges: Array<{id: string; source: string; target: string; label: string}>;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    const graph = cytoscape({
      container: ref.current,
      elements: [
        ...nodes.map(node => ({data: node})),
        ...edges.map(edge => ({data: edge})),
      ],
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "background-color": "#8a72ff",
            color: "#eef0ff",
            "text-valign": "bottom",
            "text-margin-y": 8,
            "font-size": 11,
          },
        },
        {
          selector: "edge",
          style: {
            label: "data(label)",
            "line-color": "#566078",
            "target-arrow-color": "#566078",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            color: "#aeb6cb",
            "font-size": 8,
          },
        },
      ],
      layout: {name: "cose", animate: false},
    });
    return () => graph.destroy();
  }, [nodes, edges]);

  return <div ref={ref} className="graph" aria-label="Knowledge graph"/>;
}

function Overview({alerts, loading, sources, watchlists}: {alerts: AlertRecord[]; loading: boolean; sources: SourceRecord[]; watchlists: WatchlistRecord[]}) {
  const top = alerts[0];
  return (
    <section className="grid">
      <article className="card hero">
        <p className="eyebrow">Latest intelligence</p>
        <h2>{top?.title ?? "Awaiting the first signal"}</h2>
        <p>{top?.summary ?? "Run the permitted fixture feed to create an evidence-linked alert."}</p>
        <div className="score">
          <strong>{top?.alert_score ?? 0}</strong>
          <span>Prioritization score<br/>Severity {top?.severity_code ?? 0}</span>
        </div>
        <small>{top?.stable_id ?? "No alert has been projected"}</small>
      </article>
      <article className="card">
        <h2>Workspace pulse</h2>
        <div className="metrics">
          <b>{sources.length}<span>Sources</span></b>
          <b>{watchlists.length}<span>Watchlists</span></b>
          <b>{alerts.length}<span>Alerts</span></b>
        </div>
      </article>
      <article className="card wide"><h2>Recent alerts</h2><AlertList alerts={alerts.slice(0, 8)} loading={loading}/></article>
    </section>
  );
}

function AlertList({alerts, loading, onSelect}: {alerts: AlertRecord[]; loading: boolean; onSelect?: (record: AlertRecord) => void}) {
  if (loading) return <p className="muted">Checking for alerts…</p>;
  if (!alerts.length) return <p className="muted">No alerts yet.</p>;
  return (
    <div className="list">
      {alerts.map(alert => (
        <button key={alert.id} onClick={() => onSelect?.(alert)}>
          <strong className="number">{alert.alert_score}</strong>
          <span><b>{alert.title}</b><small>{alert.summary}</small></span>
          <em>{alert.review_status}</em>
        </button>
      ))}
    </div>
  );
}

function Alerts({client, alerts, loading, reload}: {client: SignalChordClient; alerts: AlertRecord[]; loading: boolean; reload: () => Promise<void>}) {
  const [selected, setSelected] = useState<AlertRecord | null>(alerts[0] ?? null);
  useEffect(() => {
    if (!selected && alerts[0]) setSelected(alerts[0]);
  }, [alerts, selected]);

  const review = async (status: string, relevance: string) => {
    if (!selected) return;
    setSelected(await client.updateAlert(selected.id, {
      review_status: status,
      relevance_feedback: relevance,
      read_at: new Date().toISOString(),
    }));
    await reload();
  };

  return (
    <section className="split">
      <article className="card"><h2>Alert inbox</h2><AlertList alerts={alerts} loading={loading} onSelect={setSelected}/></article>
      <article className="card detail">
        {selected ? (
          <>
            {/* Field order (title -> summary -> policy -> evidence -> actions)
                matches the order a user actually asks these questions: what
                changed, why it matters, show me the proof. Resolved during
                /plan-design-review. */}
            <p className="eyebrow">Prioritization score {selected.alert_score}</p>
            <h2>{selected.title}</h2>
            <p>{selected.summary}</p>
            <p>{describePolicy(selected.policy_name)}</p>
            <p>{describeEvidenceCount(selected.evidence_ids)}</p>
            {(selected.evidence_ids.length > 0 || selected.graph_path_ids.length > 0) && (
              <details>
                <summary>{EVIDENCE_DISCLOSURE_LABEL}</summary>
                <pre>{[...selected.evidence_ids, ...selected.graph_path_ids].join("\n")}</pre>
              </details>
            )}
            <div className="actions">
              <button onClick={() => void review("verified", "relevant")}>Verify</button>
              <button onClick={() => void review("dismissed", "not_relevant")}>Dismiss</button>
            </div>
          </>
        ) : <p>Select an alert.</p>}
      </article>
    </section>
  );
}

function Entities({client}: {client: SignalChordClient}) {
  const [id, setId] = useState("company:acme");
  const [entity, setEntity] = useState<Record<string, unknown> | null>(null);
  const [timeline, setTimeline] = useState<Array<Record<string, unknown>>>([]);
  const [graph, setGraph] = useState<{
    nodes: Array<{id: string; label: string}>;
    edges: Array<{id: string; source: string; target: string; label: string}>;
  }>({nodes: [], edges: []});

  const load = async (event?: React.FormEvent) => {
    event?.preventDefault();
    const [profile, history, response] = await Promise.all([
      client.entity(id),
      client.entityTimeline(id),
      client.entityGraph(id),
    ]);
    setEntity(profile);
    setTimeline(history.items as unknown as Array<Record<string, unknown>>);
    setGraph({
      nodes: response.nodes.map(node => ({
        id: node.stable_id,
        label: String(node.display_name ?? node.title ?? node.stable_id),
      })),
      edges: response.relationships.map((edge, index) => ({
        id: edge.stable_id ?? `edge-${index}`,
        source: edge.source,
        target: edge.target,
        label: edge.type,
      })),
    });
  };

  return (
    <section className="grid">
      <article className="card">
        <h2>Entity explorer</h2>
        <form className="inline" onSubmit={load}>
          <input value={id} onChange={event => setId(event.target.value)}/><button>Load</button>
        </form>
        {entity && (
          <>
            <p className="eyebrow">{String(entity.entity_type ?? "Entity")}</p>
            <h3>{String(entity.display_name ?? entity.stable_id)}</h3>
            <p>Status {String(entity.status ?? "unknown")}</p>
          </>
        )}
      </article>
      <article className="card wide"><h2>Relationships</h2><Graph nodes={graph.nodes} edges={graph.edges}/></article>
      <article className="card wide"><h2>Timeline</h2><pre>{JSON.stringify(timeline, null, 2)}</pre></article>
    </section>
  );
}

function Watchlists({client, highlightId}: {client: SignalChordClient; highlightId?: string}) {
  const [records, setRecords] = useState<WatchlistRecord[]>([]);
  const [target, setTarget] = useState("company:acme");
  const load = useCallback(() => client.watchlists().then(setRecords), [client]);
  const highlightRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    highlightRef.current?.scrollIntoView({block: "center"});
  }, [highlightId, records]);

  const create = async () => {
    await client.createWatchlist({
      name: `Watch ${target}`,
      items: [{target_kind: "entity", target_stable_id: target, relevance_weight: 1}],
    });
    await load();
  };

  return (
    <section className="split">
      <article className="card">
        <h2>Watchlists</h2>
        {records.map(record => (
          <div
            className={record.id === highlightId ? "record highlight" : "record"}
            key={record.id}
            ref={record.id === highlightId ? highlightRef : undefined}
          >
            <b>{record.name}</b>
            {record.items.map(item => <small key={item.target_stable_id}>{item.target_stable_id}</small>)}
          </div>
        ))}
      </article>
      <article className="card">
        <h2>Add watchlist</h2>
        <label>Stable entity or topic ID<input value={target} onChange={event => setTarget(event.target.value)}/></label>
        <button className="primary" onClick={() => void create()}>Create</button>
      </article>
    </section>
  );
}

function Sources({client}: {client: SignalChordClient}) {
  const [records, setRecords] = useState<SourceRecord[]>([]);
  const load = useCallback(() => client.sources().then(setRecords), [client]);
  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section className="card page">
      <h2>Source registry</h2>
      {records.map(source => (
        <div className="record" key={source.id}>
          <div><b>{source.name}</b><small>{source.endpoint}</small></div>
          <em>{source.rights_status} · {source.enabled ? "enabled" : "disabled"}</em>
        </div>
      ))}
    </section>
  );
}

const INPUTS = {
  source_trust: .75,
  corroboration_count: 1,
  contradiction_count: 0,
  novelty: .8,
  entity_relevance: .9,
  graph_centrality: .4,
  geographic_relevance: .5,
  watchlist_match: 1,
  recency: 1,
  source_diversity: .4,
};

function Policies({client}: {client: SignalChordClient}) {
  const [records, setRecords] = useState<PolicyRecord[]>([]);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const load = useCallback(() => client.policies().then(setRecords), [client]);
  useEffect(() => {
    void load();
  }, [load]);
  const policy = records[0];

  const upload = async (file?: File) => {
    if (!file || !policy) return;
    const bytes = new Uint8Array(await file.arrayBuffer());
    let value = "";
    bytes.forEach(byte => value += String.fromCharCode(byte));
    await client.uploadPolicy(policy.id, btoa(value));
    await load();
  };

  return (
    <section className="policyStudio">
      <div className="split">
        <article className="card">
          <p className="eyebrow">SignalChord Policy Composer</p>
          <h2>{policy?.name ?? "No policy"}</h2>
          {policy?.policy_versions?.map(version => (
            <div className="record" key={version.id}>
              <b>Version {version.version_number}</b>
              <small>{version.engine} · {version.status} · {version.source_size ?? 0} bytes</small>
            </div>
          ))}
          <label className="upload">
            Upload Velato MIDI
            <input type="file" accept=".mid,.midi,audio/midi" onChange={event => void upload(event.target.files?.[0])}/>
          </label>
        </article>
        <article className="card">
          <h2>Deterministic simulation</h2>
          <button
            className="primary"
            disabled={!policy}
            onClick={() => policy && void client.simulatePolicy(policy.id, INPUTS).then(setResult)}
          >
            Run default inputs
          </button>
          {result && <pre>{JSON.stringify(result, null, 2)}</pre>}
        </article>
      </div>
      <VelatoShowcase/>
    </section>
  );
}

// Email-preference toggle — a plain labeled button (matching the .actions/
// nav/footer button vocabulary already used everywhere else in this app),
// not a generic pill/switch component, since this codebase has no
// toggle-switch precedent anywhere. Optimistic update with revert-on-failure:
// flips instantly on click, reverts with an inline error if the PATCH fails.
// Resolved during /plan-design-review (see docs/specs/explainable-alert-feed.md).
function useEmailAlertsPreference(client: SignalChordClient, initial: boolean) {
  const [enabled, setEnabled] = useState(initial);
  const [error, setError] = useState("");

  const toggle = async () => {
    const next = !enabled;
    setEnabled(next);
    setError("");
    try {
      await client.updateMe({email_alerts_enabled: next});
    } catch {
      setEnabled(!next);
      setError("Couldn't save — try again");
    }
  };

  return {enabled, error, toggle};
}

function EmailAlertsToggle({enabled, error, onToggle, className}: {
  enabled: boolean;
  error: string;
  onToggle: () => void;
  className?: string;
}) {
  return (
    <div className={className}>
      <button onClick={onToggle}>Email alerts: {enabled ? "On" : "Off"}</button>
      {error && <small className="error">{error}</small>}
    </div>
  );
}

function App({client, me, onLogout, highlightWatchlistId}: {
  client: SignalChordClient;
  me: MeResponse;
  onLogout: () => void;
  highlightWatchlistId?: string;
}) {
  // Captured once at mount (App itself only mounts once per session) — lands
  // on the Watchlists tab with the newly-created watchlist highlighted when
  // arriving straight from onboarding, Overview otherwise.
  const [view, setView] = useState<View>(() => highlightWatchlistId ? "watchlists" : "overview");
  // The realtime-gateway SSE connection authenticates via a bearer header,
  // which the web app can no longer supply now that the session lives in an
  // httpOnly cookie (that's the point — it's not JS-readable). Passing no
  // token here degrades gracefully to "Offline" (useAlerts already catches
  // the failed connection) rather than reconnecting live; extending
  // realtime-gateway itself to accept the session cookie is out of scope for
  // this change (a separate Go service) and tracked in TODOS.md.
  const {alerts, loading, live, reload} = useAlerts(client, "");
  const [sources, setSources] = useState<SourceRecord[]>([]);
  const [watchlists, setWatchlists] = useState<WatchlistRecord[]>([]);
  const emailAlerts = useEmailAlertsPreference(client, me.email_alerts_enabled ?? false);

  useEffect(() => {
    void Promise.all([client.sources(), client.watchlists()]).then(([sourceRecords, watchlistRecords]) => {
      setSources(sourceRecords);
      setWatchlists(watchlistRecords);
    });
  }, [client]);

  const logout = () => {
    void client.webLogout().finally(onLogout);
  };
  const items: Array<[View, string]> = [
    ["overview", "Overview"],
    ["entities", "Entities"],
    ["alerts", "Alerts"],
    ["watchlists", "Watchlists"],
    ["sources", "Sources"],
    ["policies", "Policy Studio"],
  ];

  return (
    <div className="shell">
      <aside>
        <div className="brand"><span>SC</span><b>SignalChord</b></div>
        <nav>
          {items.map(([id, label]) => (
            <button className={view === id ? "active" : ""} onClick={() => setView(id)} key={id}>{label}</button>
          ))}
        </nav>
        <footer>
          <small>{me.organization.name}</small>
          <b>{me.user.display_name ?? me.user.email}</b>
          <EmailAlertsToggle enabled={emailAlerts.enabled} error={emailAlerts.error} onToggle={() => void emailAlerts.toggle()}/>
          <button onClick={logout}>Sign out</button>
        </footer>
      </aside>
      <main className="workspace">
        <header>
          <div>
            <p className="eyebrow">{items.find(item => item[0] === view)?.[1]}</p>
            <h1>Real-time intelligence from connected news signals.</h1>
          </div>
          <div className="headerActions">
            {/* aside footer (with the same toggle) is hidden below 900px —
                this is the mobile-only equivalent affordance. */}
            <EmailAlertsToggle
              enabled={emailAlerts.enabled}
              error={emailAlerts.error}
              onToggle={() => void emailAlerts.toggle()}
              className="mobileSettings"
            />
            <span className={`live ${live ? "on" : "off"}`}>{live ? "Live" : "Offline"}</span>
          </div>
        </header>
        {view === "overview" && <Overview alerts={alerts} loading={loading} sources={sources} watchlists={watchlists}/>}
        {view === "entities" && <Entities client={client}/>}
        {view === "alerts" && <Alerts client={client} alerts={alerts} loading={loading} reload={reload}/>}
        {view === "watchlists" && <Watchlists client={client} highlightId={highlightWatchlistId}/>}
        {view === "sources" && <Sources client={client}/>}
        {view === "policies" && <Policies client={client}/>}
      </main>
    </div>
  );
}

// The one place the web app decides what to show once past /signup and
// /verify-email: not-logged-in -> login form; logged in with a workspace
// but no watchlist yet -> the onboarding watchlist step; otherwise the
// existing dashboard. No router library (D3c) — the step lives in local
// React state, not the URL, since none of these transitions need a
// bookmarkable link (the only one that does, email verification, is its
// own top-level route below).
function ProtectedRoute() {
  const client = useMemo(() => new SignalChordClient(API_URL), []);
  const [step, setStep] = useState<Step>({kind: "loading"});
  const [highlightWatchlistId, setHighlightWatchlistId] = useState<string | undefined>(undefined);

  const refresh = useCallback(async () => {
    try {
      setStep(stepForMe(await client.me()));
    } catch {
      setStep({kind: "login"});
    }
  }, [client]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  switch (step.kind) {
    case "loading":
      return <main className="login"><p className="muted">Loading…</p></main>;
    case "login":
      return (
        <LoginPage
          client={client}
          onWorkspaceRequired={(email, password) => setStep({kind: "workspace", email, password})}
          onAuthenticated={() => void refresh()}
        />
      );
    case "workspace":
      return (
        <OnboardingWorkspacePage
          client={client}
          email={step.email}
          password={step.password}
          onCreated={() => void refresh()}
          onBackToLogin={() => setStep({kind: "login"})}
        />
      );
    case "watchlist":
      return (
        <OnboardingWatchlistPage
          client={client}
          onCreated={(watchlistId) => {
            setHighlightWatchlistId(watchlistId);
            void refresh();
          }}
        />
      );
    case "dashboard":
      return (
        <App
          client={client}
          me={step.me}
          onLogout={() => setStep({kind: "login"})}
          highlightWatchlistId={highlightWatchlistId}
        />
      );
  }
}

function Root() {
  // The only hard requirement for a real URL is the emailed verification
  // link; everything else stays inside ProtectedRoute's own state machine.
  switch (window.location.pathname) {
    case "/signup":
      return <SignupPage/>;
    case "/verify-email":
      return <VerifyEmailPage/>;
    default:
      return <ProtectedRoute/>;
  }
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode><Root/></React.StrictMode>,
);
