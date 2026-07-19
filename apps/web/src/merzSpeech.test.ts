import {describe, expect, it} from "vitest";

import {
  estimateSpeechSeconds,
  merzSourceToSpeech,
  merzSourceToSpeechParagraphs,
  splitSpeechIntoChunks,
} from "./merzSpeech";

describe("Merzato speech translation", () => {
  const source = `# structural comment
Die Regierung beginnt bei main.
Wir nennen graph_nodes ab jetzt 9.

Zum Tagesordnungspunkt main.
  Der Bundeskanzler sagt: "SignalChord # bleibt im Zitat".
  The Greatest Fritz ruft helfer auf.
  Wenn das null ist, gehen wir zu ende.

Zum Tagesordnungspunkt helfer.
  Fritze Merz kehrt zurück.

Zum Tagesordnungspunkt ende.
  Aber ohne Bubatz.`;

  it("turns executable Merzato source into readable German prose", () => {
    const speech = merzSourceToSpeech(source);

    expect(speech).toContain("die Regierung eröffnet die Debatte");
    expect(speech).toContain("graph nodes auf 9");
    expect(speech).toContain("Redebeitrag helfer");
    expect(speech).toContain("Falls das Ergebnis null ist");
    expect(speech).toContain("SignalChord # bleibt im Zitat");
    expect(speech).not.toContain("structural comment");
  });

  it("preserves paragraph boundaries for readable display", () => {
    const paragraphs = merzSourceToSpeechParagraphs(source);
    expect(paragraphs.length).toBeGreaterThan(2);
    expect(paragraphs.every(paragraph => paragraph.trim().length > 0)).toBe(true);
  });

  it("splits long speech into mobile text-to-speech-safe chunks", () => {
    const chunks = splitSpeechIntoChunks(merzSourceToSpeech(source), 120);
    expect(chunks.length).toBeGreaterThan(1);
    expect(chunks.every(chunk => chunk.length <= 120)).toBe(true);
    expect(chunks.join(" ")).toContain("SignalChord # bleibt im Zitat");
  });

  it("estimates a non-zero speech duration", () => {
    expect(estimateSpeechSeconds(merzSourceToSpeech(source))).toBeGreaterThan(1);
  });
});
