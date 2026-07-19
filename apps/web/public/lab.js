(() => {
  "use strict";

  if (window.__signalChordLabExternalLoaded) return;
  window.__signalChordLabExternalLoaded = true;

  const SESSION_KEY = "signalchord.session.v1";
  const session = (() => {
    try { return JSON.parse(localStorage.getItem(SESSION_KEY) || "null"); }
    catch { return null; }
  })();
  const token = session?.access_token || "";
  const state = {
    nodes: [],
    relationships: [],
    sources: [],
    alerts: [],
    liveEvents: 0,
    stream: false,
    auto: true,
    history: [],
    previousNodeIds: new Set(),
    audio: null,
    speechGeneration: 0,
    speechSources: new Map(),
  };
  const $ = id => document.getElementById(id);
  const showError = message => {
    const element = $("error");
    if (!element) return;
    element.textContent = message;
    element.style.display = message ? "block" : "none";
  };
  const headers = () => ({Accept: "application/json", Authorization: `Bearer ${token}`});
  const safeFetch = async path => {
    const response = await fetch(path, {headers: headers()});
    if (!response.ok) throw new Error(`${path} returned ${response.status}`);
    return response.json();
  };

  if (!token) {
    showError("No SignalChord session is available. Sign in through the analyst workspace first, then reopen Live Lab.");
  }

  const stages = [
    ["Source registry", "permitted sources"],
    ["Kafka discovery", "source.registered / poll requested"],
    ["Document fetch", "immutable source capture"],
    ["Normalization", "versioned event contract"],
    ["NLP extraction", "entities and claims"],
    ["Neo4j projector", "tenant graph projection"],
    ["Alert projector", "policy decision persistence"],
    ["Realtime SSE", "authenticated analyst delivery"],
  ];

  function buildPipeline() {
    const pipeline = $("pipeline");
    if (!pipeline) return;
    pipeline.replaceChildren(...stages.map(([title, detail], index) => {
      const row = document.createElement("div");
      row.className = "stage";
      row.dataset.index = String(index + 1);
      const text = document.createElement("span");
      const heading = document.createElement("b");
      heading.textContent = title;
      const description = document.createElement("small");
      description.textContent = detail;
      text.append(heading, document.createElement("br"), description);
      const status = document.createElement("small");
      status.textContent = "waiting";
      row.append(text, status);
      return row;
    }));
  }

  function pipelineState() {
    const hasSource = state.sources.length > 0;
    const hasGraph = state.nodes.length > 0;
    const hasAlert = state.alerts.length > 0;
    const active = [hasSource, hasSource, hasSource, hasSource, hasGraph, hasGraph, hasAlert, state.stream];
    document.querySelectorAll(".stage").forEach((row, index) => {
      row.classList.toggle("active", active[index]);
      if (row.lastElementChild) row.lastElementChild.textContent = active[index] ? "observed" : "waiting";
    });
    const completed = active.filter(Boolean).length;
    const progress = $("pipelineProgress");
    if (progress) progress.style.width = `${Math.round(completed / active.length * 100)}%`;
  }

  function pulsePipeline() {
    document.querySelectorAll(".stage").forEach((row, index) => {
      window.setTimeout(() => {
        row.classList.remove("pulse");
        void row.offsetWidth;
        row.classList.add("pulse");
      }, index * 85);
    });
  }

  function drawGraph() {
    const edgeGroup = $("edges");
    const nodeGroup = $("nodes");
    if (!edgeGroup || !nodeGroup) return;

    const width = 900;
    const height = 480;
    const centerX = width / 2;
    const centerY = height / 2;
    const nodes = state.nodes.slice(0, 80);
    const positions = new Map();

    nodes.forEach((node, index) => {
      const ring = index === 0 ? 0 : 145 + Math.floor((index - 1) / 18) * 85;
      const slot = index === 0 ? 0 : (index - 1) % 18;
      const angle = index === 0 ? 0 : (slot / 18) * Math.PI * 2 - Math.PI / 2;
      positions.set(node.stable_id, {
        x: centerX + Math.cos(angle) * ring,
        y: centerY + Math.sin(angle) * ring,
      });
    });

    edgeGroup.replaceChildren();
    nodeGroup.replaceChildren();

    state.relationships.slice(0, 140).forEach(relationship => {
      const source = positions.get(relationship.source);
      const target = positions.get(relationship.target);
      if (!source || !target) return;
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("x1", source.x);
      line.setAttribute("y1", source.y);
      line.setAttribute("x2", target.x);
      line.setAttribute("y2", target.y);
      const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
      title.textContent = relationship.type || "relationship";
      line.append(title);
      edgeGroup.append(line);
    });

    nodes.forEach((node, index) => {
      const point = positions.get(node.stable_id);
      if (!point) return;
      const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
      const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circle.setAttribute("cx", point.x);
      circle.setAttribute("cy", point.y);
      circle.setAttribute("r", index === 0 ? 15 : 11);
      if (!state.previousNodeIds.has(node.stable_id)) circle.classList.add("fresh");
      const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
      label.classList.add("nodeLabel");
      label.setAttribute("x", point.x);
      label.setAttribute("y", point.y + 28);
      label.textContent = String(node.display_name || node.title || node.label || node.stable_id).slice(0, 36);
      const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
      title.textContent = node.stable_id;
      group.append(circle, label, title);
      nodeGroup.append(group);
    });

    state.previousNodeIds = new Set(nodes.map(node => node.stable_id));
  }

  function addHistory() {
    const item = `${new Date().toLocaleTimeString()} · ${state.nodes.length} nodes · ${state.relationships.length} relationships · ${state.alerts.length} alerts`;
    if (state.history[0] !== item) state.history.unshift(item);
    state.history = state.history.slice(0, 18);
    const growth = $("growth");
    if (!growth) return;
    growth.replaceChildren(...state.history.map(text => {
      const row = document.createElement("div");
      row.textContent = text;
      return row;
    }));
  }

  async function refresh() {
    if (!token) return;
    showError("");
    const id = $("entityId")?.value.trim() || "company:acme";
    try {
      const [graph, sources, alerts] = await Promise.all([
        safeFetch(`/api/v1/entities/${encodeURIComponent(id)}/graph`),
        safeFetch("/api/v1/sources"),
        safeFetch("/api/v1/alerts"),
      ]);
      const grew = graph.nodes.length > state.nodes.length
        || graph.relationships.length > state.relationships.length
        || alerts.length > state.alerts.length;
      state.nodes = graph.nodes || [];
      state.relationships = graph.relationships || [];
      state.sources = sources || [];
      state.alerts = alerts || [];
      if ($("nodeCount")) $("nodeCount").textContent = state.nodes.length;
      if ($("edgeCount")) $("edgeCount").textContent = state.relationships.length;
      if ($("alertCount")) $("alertCount").textContent = state.alerts.length;
      drawGraph();
      pipelineState();
      addHistory();
      if (grew) pulsePipeline();
    } catch (error) {
      showError(`Live Lab could not refresh: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  async function connectRealtime() {
    if (!token) return;
    try {
      const response = await fetch("/events", {headers: headers()});
      if (!response.ok || !response.body) throw new Error(`realtime returned ${response.status}`);
      state.stream = true;
      if ($("streamState")) {
        $("streamState").textContent = "live";
        $("streamState").style.color = "var(--mint)";
      }
      pipelineState();
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const {done, value} = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, {stream: true});
        const frames = buffer.split("\n\n");
        buffer = frames.pop() || "";
        for (const frame of frames) {
          if (!frame.trim()) continue;
          state.liveEvents += 1;
          if ($("eventCount")) $("eventCount").textContent = state.liveEvents;
          pulsePipeline();
          void refresh();
        }
      }
    } catch {
      state.stream = false;
      if ($("streamState")) {
        $("streamState").textContent = "polling";
        $("streamState").style.color = "var(--amber)";
      }
      pipelineState();
      window.setTimeout(connectRealtime, 5000);
    }
  }

  async function loadSources() {
    try {
      const entries = await Promise.all([
        ["meme-cabinet", "/programs/merz/meme-cabinet.merz"],
        ["graph-growth-briefing", "/programs/merz/graph-growth-briefing.merz"],
      ].map(async ([id, path]) => {
        const response = await fetch(path);
        if (!response.ok) throw new Error(`${id} source returned ${response.status}`);
        return [id, await response.text()];
      }));
      entries.forEach(([id, source]) => state.speechSources.set(id, source));
      const velatoResponse = await fetch("/programs/velato/live-graph-minute.vasm");
      if (!velatoResponse.ok) throw new Error("Velato source unavailable");
      if ($("merzSource")) $("merzSource").textContent = state.speechSources.get("meme-cabinet") || "";
      if ($("velatoSource")) $("velatoSource").textContent = await velatoResponse.text();
      updateSpeechTranscript();
    } catch (error) {
      showError(error instanceof Error ? error.message : String(error));
    }
  }

  function stripComment(line) {
    let quote = null;
    let escaped = false;
    for (let index = 0; index < line.length; index += 1) {
      const character = line[index];
      if (escaped) { escaped = false; continue; }
      if (character === "\\") { escaped = true; continue; }
      if (quote) { if (character === quote) quote = null; continue; }
      if (character === '"' || character === "'") { quote = character; continue; }
      if (character === "#" || character === ";" || (character === "/" && line[index + 1] === "/")) return line.slice(0, index);
    }
    return line;
  }

  function humanize(value) {
    return value.replace(/^\$/, "").replace(/[_-]+/g, " ").replace(/\br(\d+)\b/gi, "Ministerium $1").trim();
  }

  function translateStatement(statement) {
    let match = statement.match(/^Die Regierung beginnt bei ([A-Za-z_][\w.-]*)\.$/i);
    if (match) return "Meine Damen und Herren, die Regierung eröffnet die Debatte.";
    match = statement.match(/^Zum Tagesordnungspunkt ([A-Za-z_][\w.-]*)\.$/i);
    if (match) return match[1].toLowerCase() === "main" ? "Kommen wir zum Hauptteil der Rede." : `Kommen wir nun zum Tagesordnungspunkt ${humanize(match[1])}.`;
    match = statement.match(/^Wir nennen ([A-Za-z_][\w.-]*) ab jetzt (.+)\.$/i);
    if (match) return `Für diese Debatte setzen wir ${humanize(match[1])} auf ${humanize(match[2])}.`;
    match = statement.match(/^(?:Wir rufen jetzt|The Greatest Fritz ruft) ([A-Za-z_][\w.-]*) auf\.$/i);
    if (match) return `Jetzt rufen wir den Redebeitrag ${humanize(match[1])} auf.`;
    match = statement.match(/^(?:Wir gehen jetzt ohne weitere Debatte|Brandmauer) zu ([A-Za-z_][\w.-]*)\.$/i);
    if (match) return `Ohne weitere Debatte wechseln wir zum Abschnitt ${humanize(match[1])}.`;
    match = statement.match(/^Wenn das null ist, gehen wir zu ([A-Za-z_][\w.-]*)\.$/i);
    if (match) return `Falls das Ergebnis null ist, wechseln wir zum Abschnitt ${humanize(match[1])}.`;
    match = statement.match(/^Wenn das nicht null ist, gehen wir zu ([A-Za-z_][\w.-]*)\.$/i);
    if (match) return `Falls das Ergebnis nicht null ist, wechseln wir zum Abschnitt ${humanize(match[1])}.`;
    match = statement.match(/^Im ersten Wahlgang gescheitert, weiter zu ([A-Za-z_][\w.-]*)\.$/i);
    if (match) return `Wenn der erste Wahlgang scheitert, geht es weiter zum Abschnitt ${humanize(match[1])}.`;
    match = statement.match(/^Im zweiten Wahlgang geht es zu ([A-Za-z_][\w.-]*)\.$/i);
    if (match) return `Im zweiten Wahlgang geht es weiter zum Abschnitt ${humanize(match[1])}.`;
    if (/^(Wir kehren zur vorherigen Debatte zurück|Fritze Merz kehrt zurück)\.$/i.test(statement)) return "Damit kehren wir zur vorherigen Debatte zurück.";
    if (/^(Wir beenden diese Debatte|Aber ohne Bubatz)\.$/i.test(statement)) return "Damit ist diese Debatte beendet.";
    return statement.replace(/\$([A-Za-z_][\w.-]*)/g, (_, identifier) => humanize(identifier)).replace(/\br(\d+)\b/gi, "Ministerium $1");
  }

  function sourceToSpeech(source) {
    const paragraphs = [];
    let current = [];
    const flush = () => {
      if (!current.length) return;
      paragraphs.push(current.join(" "));
      current = [];
    };
    source.split(/\r?\n/).forEach(rawLine => {
      const statement = stripComment(rawLine).trim();
      if (!statement) { flush(); return; }
      current.push(translateStatement(statement));
    });
    flush();
    return paragraphs;
  }

  function splitSpeech(text, maximumLength = 220) {
    const sentences = text.replace(/\s+/g, " ").trim().match(/[^.!?]+[.!?]+|[^.!?]+$/g)?.map(sentence => sentence.trim()).filter(Boolean) || [];
    const chunks = [];
    let current = "";
    sentences.forEach(sentence => {
      const candidate = current ? `${current} ${sentence}` : sentence;
      if (candidate.length > maximumLength && current) { chunks.push(current); current = sentence; }
      else current = candidate;
    });
    if (current) chunks.push(current);
    return chunks;
  }

  function installSpeechUi() {
    const source = $("merzSource");
    const card = source?.closest("article.card");
    if (!source || !card || $("speechReader")) return;

    const style = document.createElement("style");
    style.textContent = ".speechReader{margin:0 20px 18px;padding:15px;border:1px solid rgba(101,227,187,.25);border-radius:14px;background:rgba(40,150,115,.08)}.speechReaderHead{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}.speechReaderControls{display:flex;gap:8px;flex-wrap:wrap}.speechReader select{color:#fff;background:#090d14;border:1px solid rgba(164,176,218,.2);border-radius:10px;padding:10px}.speechTranscript{max-height:320px;overflow:auto;margin-top:12px;padding:14px;border:1px solid rgba(164,176,218,.14);border-radius:12px;background:rgba(2,4,9,.46);line-height:1.7}.speechTranscript p{margin:0 0 1em}.speechProgress{height:8px;margin-top:12px;overflow:hidden;border-radius:99px;background:rgba(255,255,255,.06)}.speechProgress span{display:block;width:0;height:100%;background:linear-gradient(90deg,#8066ff,#59d9ff,#65e3bb);transition:width .25s ease}";
    document.head.append(style);

    const section = document.createElement("section");
    section.id = "speechReader";
    section.className = "speechReader";
    const head = document.createElement("div");
    head.className = "speechReaderHead";
    const title = document.createElement("div");
    const strong = document.createElement("strong");
    strong.textContent = "Readable .merz speech";
    const description = document.createElement("small");
    description.className = "muted";
    description.textContent = "Structural code is translated into a natural German speech transcript.";
    title.append(strong, document.createElement("br"), description);
    const controls = document.createElement("div");
    controls.className = "speechReaderControls";
    const select = document.createElement("select");
    select.id = "speechProgram";
    [["meme-cabinet", "Complete meme cabinet"], ["graph-growth-briefing", "Graph growth briefing"]].forEach(([value, label]) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      select.append(option);
    });
    const readButton = document.createElement("button");
    readButton.id = "readSpeech";
    readButton.className = "primary";
    readButton.textContent = "🔊 Read speech aloud";
    const stopButton = document.createElement("button");
    stopButton.id = "stopSpeech";
    stopButton.textContent = "■ Stop speech";
    stopButton.disabled = true;
    controls.append(select, readButton, stopButton);
    head.append(title, controls);
    const progress = document.createElement("div");
    progress.className = "speechProgress";
    const progressBar = document.createElement("span");
    progressBar.id = "speechProgressBar";
    progress.append(progressBar);
    const details = document.createElement("details");
    details.open = true;
    const summary = document.createElement("summary");
    summary.textContent = "Read translated speech as text";
    const transcript = document.createElement("div");
    transcript.id = "speechTranscript";
    transcript.className = "speechTranscript";
    details.append(summary, transcript);
    section.append(head, progress, details);
    source.before(section);

    select.addEventListener("change", () => {
      stopSpeech();
      const selectedSource = state.speechSources.get(select.value) || "";
      source.textContent = selectedSource;
      updateSpeechTranscript();
    });
    readButton.addEventListener("click", readSpeech);
    stopButton.addEventListener("click", stopSpeech);
  }

  function updateSpeechTranscript() {
    const transcript = $("speechTranscript");
    const select = $("speechProgram");
    if (!transcript || !select) return;
    const paragraphs = sourceToSpeech(state.speechSources.get(select.value) || "");
    transcript.replaceChildren(...paragraphs.map(text => {
      const paragraph = document.createElement("p");
      paragraph.textContent = text;
      return paragraph;
    }));
  }

  function stopSpeech(completed = false) {
    state.speechGeneration += 1;
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    if ($("readSpeech")) $("readSpeech").disabled = false;
    if ($("stopSpeech")) $("stopSpeech").disabled = true;
    if ($("speechProgressBar")) $("speechProgressBar").style.width = completed ? "100%" : "0";
  }

  function readSpeech() {
    if (!("speechSynthesis" in window) || !("SpeechSynthesisUtterance" in window)) {
      showError("Text-to-speech is unavailable in this browser. You can still read the translated transcript.");
      return;
    }
    const select = $("speechProgram");
    const paragraphs = sourceToSpeech(state.speechSources.get(select?.value || "meme-cabinet") || "");
    const chunks = splitSpeech(paragraphs.join(" "));
    if (!chunks.length) return;

    stopSpeech(false);
    const generation = state.speechGeneration;
    let index = 0;
    if ($("readSpeech")) $("readSpeech").disabled = true;
    if ($("stopSpeech")) $("stopSpeech").disabled = false;
    const voices = window.speechSynthesis.getVoices();
    const voice = voices.find(item => item.lang.toLowerCase() === "de-de") || voices.find(item => item.lang.toLowerCase().startsWith("de"));

    const next = () => {
      if (state.speechGeneration !== generation) return;
      if (index >= chunks.length) { stopSpeech(true); return; }
      const utterance = new SpeechSynthesisUtterance(chunks[index]);
      utterance.lang = voice?.lang || "de-DE";
      if (voice) utterance.voice = voice;
      utterance.rate = .92;
      utterance.pitch = .92;
      utterance.volume = 1;
      utterance.onend = () => {
        index += 1;
        if ($("speechProgressBar")) $("speechProgressBar").style.width = `${Math.round(index / chunks.length * 100)}%`;
        next();
      };
      utterance.onerror = event => {
        if (event.error !== "canceled" && event.error !== "interrupted") showError(`Speech playback stopped: ${event.error}`);
        stopSpeech(false);
      };
      window.speechSynthesis.speak(utterance);
    };
    next();
  }

  const voices = ["triangle", "sine", "square", "sawtooth"];
  const bankOperations = [
    ["HALT", "PUSH_CONST", "LOAD_INPUT", "ADD", "SUB", "MUL", "GT", "SELECT", "STORE_SCORE", "STORE_SEVERITY", "STORE_ROUTE", "STORE_SUPPRESS"],
    ["MIN", "MAX", "DIV", "MOD", "NEG", "ABS", "CLAMP", "FLOOR", "CEIL", "ROUND", "POW", "SQRT"],
    ["EQ", "NE", "LT", "LTE", "GTE", "AND", "OR", "XOR", "NOT", "IS_ZERO", "BETWEEN", "SIGN"],
    ["DUP", "SWAP", "OVER", "DROP", "LOAD_LOCAL", "STORE_LOCAL", "NOP", "STACK_DEPTH", "LOAD_SCORE", "LOAD_SEVERITY", "LOAD_ROUTE", "LOAD_SUPPRESS"],
  ];
  const encoding = new Map();
  bankOperations.forEach((operations, bank) => operations.forEach((operation, interval) => encoding.set(operation, {bank, interval})));
  const parseOperations = text => text.split(/\r?\n/).map(line => line.replace(/#.*$/, "").trim()).filter(Boolean).map(line => line.split(/\s+/)[0]);

  async function createAudioContext() {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) throw new Error("This browser does not provide the Web Audio API.");
    const context = new AudioContextClass({latencyHint: "interactive"});
    const buffer = context.createBuffer(1, 1, context.sampleRate);
    const source = context.createBufferSource();
    source.buffer = buffer;
    source.connect(context.destination);
    source.start(0);
    if (context.state === "suspended") await context.resume();
    if (context.state !== "running") {
      await context.close();
      throw new Error("Audio remained suspended. Check media volume and browser audio permission.");
    }
    return context;
  }

  function stopSong(completed = false) {
    if (state.audio) {
      state.audio.oscillators.forEach(oscillator => { try { oscillator.stop(); } catch { /* already stopped */ } });
      void state.audio.context.close();
      cancelAnimationFrame(state.audio.frame);
    }
    state.audio = null;
    if ($("playSong")) $("playSong").disabled = false;
    if ($("stopSong")) $("stopSong").disabled = true;
    if ($("songBar")) $("songBar").style.width = completed ? "100%" : "0";
    if ($("songTime")) $("songTime").textContent = completed ? "1:00 / 1:00" : "0:00 / 1:00";
    if ($("currentOp")) $("currentOp").textContent = completed ? "complete" : "ready";
  }

  async function playSong() {
    stopSong(false);
    showError("");
    const operations = parseOperations($("velatoSource")?.textContent || "");
    if (!operations.length) return;
    if (operations.length !== 100) {
      showError(`Expected 100 Velato instructions but loaded ${operations.length}.`);
      return;
    }

    try {
      const context = await createAudioContext();
      const master = context.createGain();
      const compressor = context.createDynamicsCompressor();
      master.gain.setValueAtTime(.86, context.currentTime);
      compressor.threshold.setValueAtTime(-20, context.currentTime);
      compressor.knee.setValueAtTime(18, context.currentTime);
      compressor.ratio.setValueAtTime(5, context.currentTime);
      compressor.attack.setValueAtTime(.003, context.currentTime);
      compressor.release.setValueAtTime(.25, context.currentTime);
      master.connect(compressor);
      compressor.connect(context.destination);

      const start = context.currentTime + .035;
      const beat = .6;
      const oscillators = [];
      operations.forEach((operation, index) => {
        const code = encoding.get(operation) || {bank: 3, interval: 6};
        const when = start + index * beat;
        const duration = beat * .9;
        const baseMidi = 62 + code.interval;
        const baseFrequency = 440 * 2 ** ((baseMidi - 69) / 12);
        [[1, 1], [2, .34]].forEach(([ratio, layer]) => {
          const oscillator = context.createOscillator();
          const gain = context.createGain();
          const filter = context.createBiquadFilter();
          oscillator.type = voices[code.bank] || "triangle";
          oscillator.frequency.setValueAtTime(baseFrequency * ratio, when);
          filter.type = "lowpass";
          filter.frequency.setValueAtTime(ratio === 1 ? 4200 : 5200, when);
          gain.gain.setValueAtTime(.0001, when);
          gain.gain.exponentialRampToValueAtTime((index % 4 === 0 ? .16 : .11) * layer, when + .014);
          gain.gain.exponentialRampToValueAtTime(.0001, when + duration * .92);
          oscillator.connect(filter);
          filter.connect(gain);
          gain.connect(master);
          oscillator.start(when);
          oscillator.stop(when + duration);
          oscillators.push(oscillator);
        });
      });

      if ($("playSong")) $("playSong").disabled = true;
      if ($("stopSong")) $("stopSong").disabled = false;
      state.audio = {context, oscillators, frame: 0};
      const tick = () => {
        if (!state.audio) return;
        const elapsed = Math.max(0, context.currentTime - start);
        const total = operations.length * beat;
        const index = Math.min(operations.length - 1, Math.floor(elapsed / beat));
        if ($("songBar")) $("songBar").style.width = `${Math.min(100, elapsed / total * 100)}%`;
        if ($("songTime")) $("songTime").textContent = `0:${String(Math.min(59, Math.floor(elapsed))).padStart(2, "0")} / 1:00`;
        if ($("currentOp")) $("currentOp").textContent = operations[index] || "complete";
        if (elapsed >= total) { stopSong(true); return; }
        state.audio.frame = requestAnimationFrame(tick);
      };
      state.audio.frame = requestAnimationFrame(tick);
    } catch (error) {
      showError(error instanceof Error ? error.message : String(error));
      stopSong(false);
    }
  }

  function replaceButton(id, listener) {
    const original = $(id);
    if (!original) return;
    const replacement = original.cloneNode(true);
    original.replaceWith(replacement);
    replacement.addEventListener("click", listener);
  }

  buildPipeline();
  installSpeechUi();
  replaceButton("playSong", () => void playSong());
  replaceButton("stopSong", () => stopSong(false));
  $("refresh")?.addEventListener("click", refresh);
  $("entityId")?.addEventListener("keydown", event => { if (event.key === "Enter") void refresh(); });
  $("auto")?.addEventListener("click", () => {
    state.auto = !state.auto;
    $("auto").textContent = `Auto refresh: ${state.auto ? "on" : "off"}`;
  });
  document.querySelectorAll("[data-copy]").forEach(button => {
    button.addEventListener("click", async () => {
      await navigator.clipboard.writeText($(button.dataset.copy)?.textContent || "");
      const previous = button.textContent;
      button.textContent = "Copied";
      window.setTimeout(() => { button.textContent = previous; }, 1200);
    });
  });
  window.setInterval(() => { if (state.auto) void refresh(); }, 5000);

  void loadSources();
  void refresh();
  void connectRealtime();
})();
