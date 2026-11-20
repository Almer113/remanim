// Node 24 runs this directly (type stripping): node checks/backoff_check.ts
// The reconnect waits double from 1 s and stop at 10 s (Phase 7 step 14).
import { reconnectDelay } from "../src/api.ts";

const got = [0, 1, 2, 3, 4, 5, 20].map(reconnectDelay);
const want = [1000, 2000, 4000, 8000, 10000, 10000, 10000];
if (JSON.stringify(got) !== JSON.stringify(want)) {
  console.log(`reconnect delays ${JSON.stringify(got)}, want ${JSON.stringify(want)}`);
  process.exit(1);
}
console.log("backoff ok");
