import React, {useCallback, useEffect, useMemo, useRef, useState} from "react";
import {createRoot} from "react-dom/client";
import cytoscape from "cytoscape";
import {
  AlertRecord,
  PolicyRecord,
  SessionResponse,
  SignalChordClient,
  SourceRecord,
  WatchlistRecord,
} from "@signalchord/api-client";
import {VelatoShowcase} from "./VelatoShowcase";
import "./styles.css";

type View = "overview" | "entities" | "alerts" | "watchlists" | "sources" | "policies";
const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:3000";
const REALTIME_URL = import.meta.env.VITE_REALTIME_URL ?? "http://localhost:8088";
const SESSION_KEY = "signalchord.session.v1";

function storedSession(): SessionResponse | null {
  try {
    return JSON.parse(localStorage.getItem(SESSION_KEY) ?? "null") as SessionResponse | null;
  } catch {
    return null;
  }
}

function Login({onSession}: {onSession: (value: SessionResponse) => void}) {
  const client = useMemo(() => new SignalChordClient(API_URL), []);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [organization, setOrganization] = useState("");
  const [error, setError] = useState("");

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      const session = await client.createSession(email, password, organization);
      localStorage.setItem(SESSION_KEY, JSON.stringify(session));
      onSession(session);
    } catch {
      setError("Sign-in failed. Verify that the Rails control plane is running.");
    }
  };

  return (
    <main className="login">
      <form className="card loginCard" onSubmit={submit}>
        <span className="logo">SC</span>
        <p className="eyebrow">SignalChord v1.0</p>
        <h1>Connected news intelligence.</h1>
        <p className="muted">Evidence-first monitoring for analysts.</p>
        <label>
          Email
          <input
            value={email}
            onChange={event => setEmail(event.target.value)}
            type="email"
            autoComplete="username"
            placeholder="analyst@signalchord.local"
            required
          />
        </label>
        <label>
          Password
          <input
            value={password}
            onChange={event => setPassword(event.target.value)}
            type="password"
            autoComplete="current-password"
            placeholder="Local development password"
            required
          />
        </label>
        <label>
          Organization
          <input
            value={organization}
            onChange={event => setOrganization(event.target.value)}
            autoComplete="organization"
            placeholder="demo"
            required
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button className="primary">Sign in</button>
      </form>
    </main>
  );
}

function useAlerts(client: SignalChordClient, token: string) {
  const [alerts, setAlerts] = useState<AlertRecord[]>([]);
  const [live, setLive] = useState(false);
  const load = useCallback(() => client.alerts().then(setAlerts), [client]);

  useEffect(() => {
    void load();
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

  return {alerts, live, reload: load};
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

function Overview({alerts, sources, watchlists}: {alerts: AlertRecord[]; sources: SourceRecord[]; watchlists: WatchlistRecord[]}) {
  const top = alerts[0];
  return (
    <section className="grid">
      <article className="card hero">
        <p className="eyebrow">Latest intelligence</p>
        <h2>{top?.title ?? "Awaiting the first signal"}</h2>
        <p>{top?.summary ?? "Run the permitted fixture feed to create an evidence-linked alert."}</p>
        <div className="score">
          <strong>{top?.alert_score ?? 0}</strong>
          <span>Policy score<br/>Severity {top?.severity_code ?? 0}</span>
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
      <article className="card wide"><h2>Recent alerts</h2><AlertList alerts={alerts.slice(0, 8)}/></article>
    </section>
  );
}

function AlertList({alerts, onSelect}: {alerts: AlertRecord[]; onSelect?: (record: AlertRecord) => void}) {
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

function Alerts({client, alerts, reload}: {client: SignalChordClient; alerts: AlertRecord[]; reload: () => Promise<void>}) {
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
      <article className="card"><h2>Alert inbox</h2><AlertList alerts={alerts} onSelect={setSelected}/></article>
      <article className="card detail">
        {selected ? (
          <>
            <p className="eyebrow">Score {selected.alert_score}</p>
            <h2>{selected.title}</h2>
            <p>{selected.summary}</p>
            <h3>Evidence IDs</h3>
            <pre>{selected.evidence_ids.join("\n") || "No evidence"}</pre>
            <h3>Graph path IDs</h3>
            <pre>{selected.graph_path_ids.join("\n") || "No paths"}</pre>
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

function Watchlists({client}: {client: SignalChordClient}) {
  const [records, setRecords] = useState<WatchlistRecord[]>([]);
  const [target, setTarget] = useState("company:acme");
  const load = useCallback(() => client.watchlists().then(setRecords), [client]);

  useEffect(() => {
    void load();
  }, [load]);

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
          <div className="record" key={record.id}>
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

function App() {
  const [session, setSession] = useState<SessionResponse | null>(storedSession);
  const [view, setView] = useState<View>("overview");
  const client = useMemo(() => new SignalChordClient(API_URL, session?.access_token), [session]);
  const {alerts, live, reload} = useAlerts(client, session?.access_token ?? "");
  const [sources, setSources] = useState<SourceRecord[]>([]);
  const [watchlists, setWatchlists] = useState<WatchlistRecord[]>([]);

  useEffect(() => {
    if (session) {
      void Promise.all([client.sources(), client.watchlists()]).then(([sourceRecords, watchlistRecords]) => {
        setSources(sourceRecords);
        setWatchlists(watchlistRecords);
      });
    }
  }, [client, session]);

  if (!session) return <Login onSession={setSession}/>;
  const logout = () => {
    localStorage.removeItem(SESSION_KEY);
    setSession(null);
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
          <small>{session.organization.name}</small>
          <b>{session.user.display_name ?? session.user.email}</b>
          <button onClick={logout}>Sign out</button>
        </footer>
      </aside>
      <main className="workspace">
        <header>
          <div>
            <p className="eyebrow">{items.find(item => item[0] === view)?.[1]}</p>
            <h1>Real-time intelligence from connected news signals.</h1>
          </div>
          <span className={`live ${live ? "on" : "off"}`}>{live ? "Live" : "Offline"}</span>
        </header>
        {view === "overview" && <Overview alerts={alerts} sources={sources} watchlists={watchlists}/>} 
        {view === "entities" && <Entities client={client}/>} 
        {view === "alerts" && <Alerts client={client} alerts={alerts} reload={reload}/>} 
        {view === "watchlists" && <Watchlists client={client}/>} 
        {view === "sources" && <Sources client={client}/>} 
        {view === "policies" && <Policies client={client}/>} 
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode><App/></React.StrictMode>,
);
