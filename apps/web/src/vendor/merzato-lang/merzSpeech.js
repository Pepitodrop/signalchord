import { assemble } from './assembler.js';
import { MerzatoSyntaxError } from './errors.js';
import { validateProgram } from './validator.js';

function stripComment(line) {
  let quote = null;
  let escaped = false;

  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    if (escaped) {
      escaped = false;
      continue;
    }
    if (char === '\\') {
      escaped = true;
      continue;
    }
    if (quote) {
      if (char === quote) quote = null;
      continue;
    }
    if (char === '"' || char === "'") {
      quote = char;
      continue;
    }
    if (char === ';' || char === '#' || (char === '/' && line[index + 1] === '/')) {
      return line.slice(0, index);
    }
  }

  return line;
}

function syntax(message, line) {
  throw new MerzatoSyntaxError(`${message} on line ${line}`, {
    code: 'UNKNOWN_SPEECH',
    line
  });
}

const MEME_RULES = Object.freeze([
  [/^Gehobene Mittelschicht mit (.+)\.$/i, match => [`push ${match[1]}`]],
  [/^Privatflieger liefert (r(?:[0-9]|1[0-5]))\.$/i, match => [`load ${match[1]}`]],
  [/^BlackRock verwaltet (r(?:[0-9]|1[0-5]))\.$/i, match => [`store ${match[1]}`]],
  [/^Mimimi\.$/i, () => ['dup']],
  [/^Rambo Zambo\.$/i, () => ['swap']],
  [/^Mehr arbeiten\.$/i, () => ['add']],
  [/^Leistung muss sich lohnen\.$/i, () => ['add']],
  [/^Bierdeckel-Steuer\.$/i, () => ['mod']],
  [/^Brandmauer zu ([A-Za-z_][\w.-]*)\.$/i, match => [`jmp ${match[1]}`]],
  [/^Im ersten Wahlgang gescheitert, weiter zu ([A-Za-z_][\w.-]*)\.$/i, match => [`jz ${match[1]}`]],
  [/^Im zweiten Wahlgang geht es zu ([A-Za-z_][\w.-]*)\.$/i, match => [`jnz ${match[1]}`]],
  [/^The Greatest Fritz ruft ([A-Za-z_][\w.-]*) auf\.$/i, match => [`call ${match[1]}`]],
  [/^Fritze Merz kehrt zurück\.$/i, () => ['ret']],
  [/^Das iPad reagiert: (.+)\.$/i, match => [`push ${match[1]}`, 'merz "THE CRITIC SAYS"']],
  [/^Der Bundeskanzler sagt: (.+)\.$/i, match => [`push ${match[1]}`, 'merz "THE CRITIC SAYS"']],
  [/^Sosej Kanzler sagt: (.+)\.$/i, match => [`push ${match[1]}`, 'merz "THE CRITIC SAYS"']],
  [/^Kalori Kanzler sagt: (.+)\.$/i, match => [`push ${match[1]}`, 'merz "THE CRITIC SAYS"']],
  [/^Aber ohne Bubatz\.$/i, () => ['halt']],
  [/^Was ist Bubatz\?$/i, () => ['nop']],
  [/^Merz leck Eier\.$/i, () => ['nop']],
  [/^Mehrzweckeier\.$/i, () => ['nop']],
  [/^Der Bundeskanzler\.$/i, () => ['nop']],
  [/^Sosej Kanzler(?: Halal)?\.$/i, () => ['nop']],
  [/^Kalori Kanzler\.$/i, () => ['nop']],
  [/^The Greatest Fritz\.$/i, () => ['nop']],
  [/^Fritze Merz\.$/i, () => ['nop']],
  [/^Rambo Zambo im Adenauer-Haus\.$/i, () => ['nop']],
  [/^Aber erst ab 18 Uhr\.$/i, () => ['nop']],
  [/^Das iPad nickt\.$/i, () => ['nop']],
  [/^Sauerland Airlines\.$/i, () => ['nop']],
  [/^Mittelschicht mit Privatflugzeug\.$/i, () => ['nop']],
  [/^Kanzler im zweiten Versuch\.$/i, () => ['nop']],
  [/^Deutschland muss wieder arbeiten\.$/i, () => ['nop']],
  [/^Bubatz im Adenauer-Haus\.$/i, () => ['nop']],
  [/^Regierungsflieger statt Privatflieger\.$/i, () => ['nop']]
]);

const RULES = Object.freeze([
  ...MEME_RULES,
  [/^Die Regierung beginnt bei ([A-Za-z_][\w.-]*)\.$/i, match => [`.entry ${match[1]}`]],
  [/^Zum Tagesordnungspunkt ([A-Za-z_][\w.-]*)\.$/i, match => [`${match[1]}:`]],
  [/^Wir nennen ([A-Za-z_][\w.-]*) ab jetzt (.+)\.$/i, match => [`.const ${match[1]} ${match[2]}`]],
  [/^Wir brauchen jetzt (.+)\.$/i, match => [`push ${match[1]}`]],
  [/^Das nehmen wir wieder vom Tisch\.$/i, () => ['pop']],
  [/^Das sage ich ganz bewusst noch einmal\.$/i, () => ['dup']],
  [/^Wir drehen die Reihenfolge um\.$/i, () => ['swap']],
  [/^Wir rechnen das zusammen, denn Leistung muss sich lohnen\.$/i, () => ['add']],
  [/^Wir ziehen das ab, damit der Haushalt stimmt\.$/i, () => ['sub']],
  [/^Wir vervielfachen das für den Wirtschaftsstandort\.$/i, () => ['mul']],
  [/^Wir teilen das durch, solide finanziert\.$/i, () => ['div']],
  [/^Der Rest bleibt unter der Schuldenbremse\.$/i, () => ['mod']],
  [/^Das Gegenteil ist jetzt richtig\.$/i, () => ['not']],
  [/^Wir prüfen, ob das erste größer ist\.$/i, () => ['cmpgt']],
  [/^Aus dem Ministerium (r(?:[0-9]|1[0-5])) wird geliefert\.$/i, match => [`load ${match[1]}`]],
  [/^Das kommt jetzt in das Ministerium (r(?:[0-9]|1[0-5]))\.$/i, match => [`store ${match[1]}`]],
  [/^Wir holen das aus dem Bundesarchiv\.$/i, () => ['hload']],
  [/^Wir legen das im Bundesarchiv ab\.$/i, () => ['hstore']],
  [/^Wir gehen jetzt ohne weitere Debatte zu ([A-Za-z_][\w.-]*)\.$/i, match => [`jmp ${match[1]}`]],
  [/^Wenn das null ist, gehen wir zu ([A-Za-z_][\w.-]*)\.$/i, match => [`jz ${match[1]}`]],
  [/^Wenn das nicht null ist, gehen wir zu ([A-Za-z_][\w.-]*)\.$/i, match => [`jnz ${match[1]}`]],
  [/^Wir rufen jetzt ([A-Za-z_][\w.-]*) auf\.$/i, match => [`call ${match[1]}`]],
  [/^Wir kehren zur vorherigen Debatte zurück\.$/i, () => ['ret']],
  [/^Wir formulieren das jetzt als Text\.$/i, () => ['tostr']],
  [/^Wir führen diese Aussagen zusammen\.$/i, () => ['concat']],
  [/^Die Zahl muss jetzt raus\.$/i, () => ['outn']],
  [/^Der Buchstabe muss jetzt raus\.$/i, () => ['outc']],
  [/^Das Kanzleramt ordnet an: (.+)\.$/i, match => [`merz ${match[1]}`]],
  [/^Ich sage ganz klar: (.+)\.$/i, match => [`push ${match[1]}`, 'merz "THE CRITIC SAYS"']],
  [/^Wir beenden diese Debatte\.$/i, () => ['halt']],
  [/^Dazu sage ich heute nichts\.$/i, () => ['nop']]
]);

function transpileWithOrigins(source) {
  if (typeof source !== 'string') throw new TypeError('Merz speech source must be a string');

  const output = [];
  const origins = [];
  const lines = source.split(/\r?\n/);

  for (let lineNumber = 1; lineNumber <= lines.length; lineNumber += 1) {
    const statement = stripComment(lines[lineNumber - 1]).trim();
    if (!statement) continue;

    let translated = null;
    for (const [pattern, emit] of RULES) {
      const match = statement.match(pattern);
      if (match) {
        translated = emit(match);
        break;
      }
    }

    if (!translated) {
      syntax(`I do not understand this Merz-style statement: '${statement}'`, lineNumber);
    }

    for (const assemblyLine of translated) {
      output.push(assemblyLine);
      origins.push(lineNumber);
    }
  }

  return {
    assembly: output.join('\n'),
    origins
  };
}

export function transpileMerzSpeech(source) {
  return transpileWithOrigins(source).assembly;
}

export function compileMerzSpeech(source, { filename = '<memory>' } = {}) {
  const { assembly, origins } = transpileWithOrigins(source);
  const assembled = assemble(assembly, { filename });
  const instructions = assembled.instructions.map(instruction => ({
    ...instruction,
    generatedLine: instruction.line,
    line: origins[(instruction.line ?? 1) - 1] ?? instruction.line
  }));

  return validateProgram({
    ...assembled,
    instructions,
    sourceType: 'merz-speech',
    generatedAssembly: assembly
  }, { freeze: true });
}

export const MERZ_MEME_RULES = MEME_RULES;
export const MERZ_SPEECH_RULES = RULES;
