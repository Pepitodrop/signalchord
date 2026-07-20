// @vitest-environment jsdom
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";

// Regression: ISSUE-001 — Copy .merz button gave no feedback when
// navigator.clipboard.writeText() rejected (button text never updated, no
// error surfaced). Found by /qa on 2026-07-20.
// Report: .gstack/qa-reports/qa-report-signalchord-luisbenedikt-de-2026-07-20.md

const LAB_JS_MODULE = "../public/lab.js";

type LabWindow = Window & {__signalChordLabExternalLoaded?: boolean};

async function loadLabScript() {
  vi.resetModules();
  (window as LabWindow).__signalChordLabExternalLoaded = false;
  await import(LAB_JS_MODULE);
}

describe("Live Lab copy button", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div id="error"></div>
      <pre id="merzSource">sample merz source</pre>
      <button data-copy="merzSource">Copy .merz</button>
    `;
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ok: true, text: async () => "stub-source"})),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    delete (window as LabWindow).__signalChordLabExternalLoaded;
  });

  it("shows success feedback when the clipboard write resolves", async () => {
    Object.defineProperty(navigator, "clipboard", {
      value: {writeText: vi.fn().mockResolvedValue(undefined)},
      configurable: true,
    });

    await loadLabScript();
    const button = document.querySelector<HTMLButtonElement>("[data-copy]")!;
    button.click();

    await vi.waitFor(() => expect(button.textContent).toBe("Copied"));
  });

  it("shows failure feedback and surfaces the error when the clipboard write is rejected", async () => {
    Object.defineProperty(navigator, "clipboard", {
      value: {
        writeText: vi.fn().mockRejectedValue(new Error("Write permission denied")),
      },
      configurable: true,
    });

    await loadLabScript();
    const button = document.querySelector<HTMLButtonElement>("[data-copy]")!;
    button.click();

    await vi.waitFor(() => expect(button.textContent).toBe("Copy failed"));

    const errorBanner = document.getElementById("error")!;
    expect(errorBanner.textContent).toContain("Write permission denied");
    expect(errorBanner.style.display).toBe("block");
  });
});
