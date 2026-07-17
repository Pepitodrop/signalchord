import type {Program} from "./assembler.js";

export interface MerzSpeechProgram extends Program {
  sourceType: "merz-speech";
  generatedAssembly: string;
}

export function transpileMerzSpeech(source: string): string;
export function compileMerzSpeech(source: string, options?: {filename?: string}): MerzSpeechProgram;
export const MERZ_MEME_RULES: readonly unknown[];
export const MERZ_SPEECH_RULES: readonly unknown[];
