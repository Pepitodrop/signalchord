function stripComment(line: string): string {
  let quote: string | null = null;
  let escaped = false;

  for (let index = 0; index < line.length; index += 1) {
    const character = line[index];
    if (escaped) {
      escaped = false;
      continue;
    }
    if (character === "\\") {
      escaped = true;
      continue;
    }
    if (quote) {
      if (character === quote) quote = null;
      continue;
    }
    if (character === '"' || character === "'") {
      quote = character;
      continue;
    }
    if (character === "#" || character === ";" || (character === "/" && line[index + 1] === "/")) {
      return line.slice(0, index);
    }
  }

  return line;
}

function humanizeIdentifier(value: string): string {
  return value
    .replace(/^\$/, "")
    .replace(/[_-]+/g, " ")
    .replace(/\br(\d+)\b/gi, "Ministerium $1")
    .trim();
}

function spokenStatement(statement: string): string | null {
  let match = statement.match(/^Die Regierung beginnt bei ([A-Za-z_][\w.-]*)\.$/i);
  if (match) return "Meine Damen und Herren, die Regierung eröffnet die Debatte.";

  match = statement.match(/^Zum Tagesordnungspunkt ([A-Za-z_][\w.-]*)\.$/i);
  if (match) {
    const name = humanizeIdentifier(match[1]);
    if (name.toLowerCase() === "main") return "Kommen wir zum Hauptteil der Rede.";
    return `Kommen wir nun zum Tagesordnungspunkt ${name}.`;
  }

  match = statement.match(/^Wir nennen ([A-Za-z_][\w.-]*) ab jetzt (.+)\.$/i);
  if (match) return `Für diese Debatte setzen wir ${humanizeIdentifier(match[1])} auf ${humanizeIdentifier(match[2])}.`;

  match = statement.match(/^Wir rufen jetzt ([A-Za-z_][\w.-]*) auf\.$/i);
  if (match) return `Jetzt rufen wir den Redebeitrag ${humanizeIdentifier(match[1])} auf.`;

  match = statement.match(/^The Greatest Fritz ruft ([A-Za-z_][\w.-]*) auf\.$/i);
  if (match) return `The Greatest Fritz ruft jetzt den Redebeitrag ${humanizeIdentifier(match[1])} auf.`;

  match = statement.match(/^Wir gehen jetzt ohne weitere Debatte zu ([A-Za-z_][\w.-]*)\.$/i);
  if (match) return `Ohne weitere Debatte wechseln wir zum Abschnitt ${humanizeIdentifier(match[1])}.`;

  match = statement.match(/^Brandmauer zu ([A-Za-z_][\w.-]*)\.$/i);
  if (match) return `Wir ziehen die Brandmauer und wechseln zum Abschnitt ${humanizeIdentifier(match[1])}.`;

  match = statement.match(/^Wenn das null ist, gehen wir zu ([A-Za-z_][\w.-]*)\.$/i);
  if (match) return `Falls das Ergebnis null ist, wechseln wir zum Abschnitt ${humanizeIdentifier(match[1])}.`;

  match = statement.match(/^Wenn das nicht null ist, gehen wir zu ([A-Za-z_][\w.-]*)\.$/i);
  if (match) return `Falls das Ergebnis nicht null ist, wechseln wir zum Abschnitt ${humanizeIdentifier(match[1])}.`;

  match = statement.match(/^Im ersten Wahlgang gescheitert, weiter zu ([A-Za-z_][\w.-]*)\.$/i);
  if (match) return `Wenn der erste Wahlgang scheitert, geht es weiter zum Abschnitt ${humanizeIdentifier(match[1])}.`;

  match = statement.match(/^Im zweiten Wahlgang geht es zu ([A-Za-z_][\w.-]*)\.$/i);
  if (match) return `Im zweiten Wahlgang geht es weiter zum Abschnitt ${humanizeIdentifier(match[1])}.`;

  if (/^(Wir kehren zur vorherigen Debatte zurück|Fritze Merz kehrt zurück)\.$/i.test(statement)) {
    return "Damit kehren wir zur vorherigen Debatte zurück.";
  }
  if (/^(Wir beenden diese Debatte|Aber ohne Bubatz)\.$/i.test(statement)) {
    return "Damit ist diese Debatte beendet.";
  }

  return statement
    .replace(/\$([A-Za-z_][\w.-]*)/g, (_, identifier: string) => humanizeIdentifier(identifier))
    .replace(/\br(\d+)\b/gi, "Ministerium $1");
}

export function merzSourceToSpeechParagraphs(source: string): string[] {
  const paragraphs: string[] = [];
  let current: string[] = [];

  const flush = () => {
    if (!current.length) return;
    paragraphs.push(current.join(" "));
    current = [];
  };

  for (const rawLine of source.split(/\r?\n/)) {
    const statement = stripComment(rawLine).trim();
    if (!statement) {
      flush();
      continue;
    }
    const spoken = spokenStatement(statement);
    if (spoken) current.push(spoken);
  }
  flush();

  return paragraphs;
}

export function merzSourceToSpeech(source: string): string {
  return merzSourceToSpeechParagraphs(source).join("\n\n");
}

export function splitSpeechIntoChunks(text: string, maximumLength = 220): string[] {
  if (!Number.isInteger(maximumLength) || maximumLength < 80) {
    throw new Error("Speech chunk length must be an integer of at least 80 characters.");
  }

  const sentences = text
    .replace(/\s+/g, " ")
    .trim()
    .match(/[^.!?]+[.!?]+|[^.!?]+$/g)
    ?.map(sentence => sentence.trim())
    .filter(Boolean) ?? [];
  const chunks: string[] = [];
  let current = "";

  for (const sentence of sentences) {
    if (sentence.length > maximumLength) {
      if (current) {
        chunks.push(current);
        current = "";
      }
      const words = sentence.split(/\s+/);
      let longChunk = "";
      for (const word of words) {
        const candidate = longChunk ? `${longChunk} ${word}` : word;
        if (candidate.length > maximumLength && longChunk) {
          chunks.push(longChunk);
          longChunk = word;
        } else {
          longChunk = candidate;
        }
      }
      if (longChunk) chunks.push(longChunk);
      continue;
    }

    const candidate = current ? `${current} ${sentence}` : sentence;
    if (candidate.length > maximumLength && current) {
      chunks.push(current);
      current = sentence;
    } else {
      current = candidate;
    }
  }

  if (current) chunks.push(current);
  return chunks;
}

export function estimateSpeechSeconds(text: string, wordsPerMinute = 135): number {
  const words = text.trim().split(/\s+/).filter(Boolean).length;
  return Math.max(1, Math.round(words / Math.max(60, wordsPerMinute) * 60));
}
