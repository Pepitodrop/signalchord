import React, {useEffect, useRef} from "react";
import {createRoot} from "react-dom/client";
import cytoscape from "cytoscape";
import "./styles.css";

const evidence = [
  {source:"Example Technology Wire", type:"source report", confidence:1, text:"Acme announced a partnership with Northstar Labs."},
  {source:"SignalChord NLP v0.1", type:"model extraction", confidence:0.91, text:"PARTNERED_WITH(Acme, Northstar Labs)"},
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

function App() {
  return <main>
    <header><div><span className="eyebrow">SignalChord</span><h1>Real-time intelligence from connected news signals.</h1></div><button>⌘ K Search</button></header>
    <section className="grid">
      <article className="panel hero"><p className="label">Watched entity</p><h2>Acme Corporation</h2><p className="muted">Company · model verified · updated 42 seconds ago</p><div className="score"><strong>86</strong><span>Alert score<br/>High severity</span></div><p>New cross-source evidence indicates a partnership with Northstar Labs. The relationship is supported by one source and awaits corroboration.</p></article>
      <article className="panel"><div className="panelTitle"><h3>Relationship graph</h3><span>Last 24 hours</span></div><Graph/></article>
      <article className="panel evidence"><h3>Evidence and provenance</h3>{evidence.map(item=><div className="evidenceRow" key={item.text}><div><strong>{item.source}</strong><span>{item.type}</span></div><p>{item.text}</p><b>{Math.round(item.confidence*100)}%</b></div>)}</article>
      <article className="panel"><h3>Story timeline</h3><ol><li><time>09:14</time><div><strong>Article discovered</strong><p>RSS source adapter</p></div></li><li><time>09:15</time><div><strong>Entities resolved</strong><p>2 canonical candidates</p></div></li><li><time>09:15</time><div><strong>Policy evaluated</strong><p>Default Velato policy v1</p></div></li></ol></article>
    </section>
  </main>
}
createRoot(document.getElementById("root")!).render(<React.StrictMode><App/></React.StrictMode>);
