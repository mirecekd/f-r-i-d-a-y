// frontend/src/views/highlight.ts
const KEYWORDS = new Set(
  ("def class return if elif else for while in not and or import from as with try except finally raise lambda yield " +
    "None True False pass break continue async await function const let var new this typeof switch case default " +
    "throw null true false undefined export interface type enum extends implements public private static void int " +
    "fn pub impl struct match use mut self SELECT FROM WHERE INSERT UPDATE DELETE JOIN ON GROUP BY ORDER LIMIT").split(" "),
);

type Cls = "k" | "s" | "c" | "n";
const TOKEN = /(\/\/[^\n]*|#[^\n]*|\/\*[\s\S]*?\*\/|--[^\n]*)|("(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'|`(?:\\.|[^`\\])*`)|(\b\d+(?:\.\d+)?\b)|([A-Za-z_]\w*)/g;

/** Tokenize into DOM spans (comments, strings, numbers, keywords). No innerHTML. */
export function highlight(code: string, lang: string): DocumentFragment {
  const frag = document.createDocumentFragment();
  const hashComment = !/^(js|ts|javascript|typescript|c|cpp|java|go|rust|rs|css|json)$/i.test(lang);
  let last = 0;
  const push = (text: string, cls?: Cls) => {
    if (!text) return;
    if (!cls) return void frag.append(document.createTextNode(text));
    const s = document.createElement("span");
    s.className = "hl-" + cls;
    s.textContent = text;
    frag.append(s);
  };
  for (const m of code.matchAll(TOKEN)) {
    const i = m.index ?? 0;
    let cls: Cls | undefined;
    if (m[1]) cls = m[1].startsWith("#") && !hashComment ? undefined : "c";
    else if (m[2]) cls = "s";
    else if (m[3]) cls = "n";
    else if (m[4] && KEYWORDS.has(m[4])) cls = "k";
    if (!cls) continue;
    push(code.slice(last, i));
    push(m[0], cls);
    last = i + m[0].length;
  }
  push(code.slice(last));
  return frag;
}
