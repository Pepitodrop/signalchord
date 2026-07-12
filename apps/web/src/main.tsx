import React, {useEffect, useRef, useState} from "react";
import {createRoot} from "react-dom/client";
import cytoscape from "cytoscape";
import "./styles.css";

type RealtimeEnvelope = {
  event_type: string;
  occurred_at: string;
  payload: {
    alert_id?: string;
    alert_score?: number;
    severity_code?: number;
    routing_code?: number;
    evidence_ids?: string[];
    policy_version_id?: string;
  };
};

const evidence = [
  {source:"SignalChord fixture source", type:"source report", confidence:1, text:"Acme Corporation announced a partnership with Northstar Labs."},
  {source:"SignalChord NLP v0.1", type:"model extraction", confidence:0.91, text:"PARTNERED_WITH(Acme Corporation, Northstar Labs)"},
];

function Graph() {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const cy = cytoscape({container:ref.current,elements:[
      {data:{id:"acme",label:"Acme"}},{data:{id:"northstar",label:"Northstar Labs"}},{data:{id:"article",label:"Article"}},
      {data:{id:"e1",source:"article",target:"acme",label:"MENTIONS"}},{data:{id:"e2",source:"article",target:"northstar",label:"MENTIONS"}},{data:{id:"e3",source:"acme",target:"northstar",label:"PARTNERED_WITH"}},
    ],style:[
      {selector:"node",style:{label:"data(label)","background-color":"#7557ff",color:"#eef0ff","text-valign":"bottom","text-margin-y":8,"font-size":12}},
      {selector:"edge",style:{label:"data(label)",width:2,"line-color":"#596174","target-arrow-color":"#596174","target-arrow-shape":"triangle","curve-style":"bezier","font-size":9,color:"#aeb6cb"}},
    ],layout:{name:"cose",animate:false}});
    return () => cy.destroy();
  },[]);
  return <div ref={ref} className="graph" aria-label="Interactive relationship graph"/>;
}

function useRealtimeAlert() {
  const [alert, setAlert] = useState<RealtimeEnvelope | null>(null);
  const [connected, setConnected] = useState(false);
  useEffect(() => {
    const source = new EventSource("http://localhost:8088/events?tenant_id=tenant-demo");
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);
    source.addEventListener("alert", event => {
      try {
        const parsed = JSON.parse((event as MessageEvent<string>).data) as RealtimeEnvelope;
        if (parsed.event_type === "alert.created.v1") setAlert(parsed);
      } catch {
        setConnected(false);
      }
    });
    return () => source.close();
  }, []);
  return {alert, connected};
}

function App() {
  const {alert, connected} = useRealtimeAlert();
  const score = alert?.payload.alert_score ?? 86;
  const policy = alert?.payload.policy_version_id ?? "v1";
  return <main>
    <header><div><span className="eyebrow">SignalChord</span><h1>Real-time intelligence from connected news signals.</h1></div><div className="headerActions"><span className={connected ? "live connected" : "live"}>{connected ? "Live" : "Reconnecting"}</span><button>⌘ K Search</button></div></header>
    <section className="grid">
      <article className="panel hero"><p className="label">Watched entity</p><h2>Acme Corporation</h2><p className="muted">Company · model verified · {alert ? "live event received" : "fixture preview"}</p><div className="score"><strong>{score}</strong><span>Alert score<br/>{score >= 75 ? "High" : score >= 45 ? "Medium" : "Low"} severity</span></div><p>New evidence indicates a partnership with Northstar Labs. The relationship is evidence-linked and awaits independent corroboration.</p><p className="trace">Policy {policy} · {alert?.payload.alert_id ?? "waiting for Kafka alert"}</p></article>
      <article className="panel"><div className="panelTitle"><h3>Relationship graph</h3><span>Last 24 hours</span></div><Graph/></article>
      <article className="panel evidence"><h3>Evidence and provenance</h3>{evidence.map(item=><div className="evidenceRow" key={item.text}><div><strong>{item.source}</strong><span>{item.type}</span></div><p>{item.text}</p><b>{Math.round(item.confidence*100)}%</b></div>)}</article>
      <article className="panel"><h3>Story timeline</h3><ol><li><time>09:14</time><div><strong>Article discovered</strong><p>RSS source adapter</p></div></li><li><time>09:15</time><div><strong>Entities extracted</strong><p>Evidence spans retained</p></div></li><li><time>Live</time><div><strong>Policy evaluated</strong><p>Default Velato policy {policy}</p></div></li></ol></article>
    </section>
  </main>
}
createRoot(document.getElementById("root")!).render(<React.StrictMode><App/></React.StrictMode>);
