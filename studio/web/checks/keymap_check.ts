// Node 24 runs this directly (type stripping): node checks/keymap_check.ts
// Every key combination maps to one action at most, and actionFor finds it.
import { BINDINGS, actionFor } from "../src/keymap.ts";

const seen = new Map<string, string>();
let bad = 0;
for (const b of BINDINGS) {
  for (const m of b.match) {
    for (const shift of m.shift === "any" ? [false, true] : [!!m.shift]) {
      for (const alt of m.alt === "any" ? [false, true] : [!!m.alt]) {
        for (const sel of m.sel === undefined ? [false, true] : [m.sel]) {
          const k = `${m.key}|ctrl=${!!m.ctrl}|shift=${shift}|alt=${alt}|sel=${sel}`;
          const prev = seen.get(k);
          if (prev && prev !== b.action) { console.log(`clash: ${k} → ${prev} and ${b.action}`); bad++; }
          seen.set(k, b.action);
          const ev = { key: m.key.length === 1 ? m.key : m.key[0].toUpperCase() + m.key.slice(1), ctrlKey: !!m.ctrl,
                       metaKey: false, shiftKey: shift, altKey: alt } as unknown as KeyboardEvent;
          const got = actionFor(ev, sel);
          if (got !== b.action && !prev) { console.log(`not found: ${k} → ${got}, want ${b.action}`); bad++; }
        }
      }
    }
  }
  if (!b.keys.length || !b.label) { console.log(`no keys or label: ${b.action}`); bad++; }
}
console.log(bad ? `${bad} problem(s)` : `keymap ok: ${seen.size} key combinations, ${BINDINGS.length} actions`);
process.exit(bad ? 1 : 0);
