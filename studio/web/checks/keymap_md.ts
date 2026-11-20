// Prints the shortcut table for studio/README.md: node checks/keymap_md.ts
import { BINDINGS } from "../src/keymap.ts";

const groups = [...new Set(BINDINGS.map((b) => b.group))];
const out: string[] = ["| Keys | What it does |", "|---|---|"];
for (const g of groups) {
  out.push(`| **${g}** | |`);
  for (const b of BINDINGS.filter((x) => x.group === g)) {
    out.push(`| ${b.keys.map((k) => "`" + k + "`").join(" ")} | ${b.label} |`);
  }
}
console.log(out.join("\n"));
