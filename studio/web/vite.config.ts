import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Built into dist/ and served by the studio server (python -m studio.server).
// `npm run dev` proxies the API to a running server on 8770.
export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist", emptyOutDir: true },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8770",
      "/frame": "http://127.0.0.1:8770",
      "/objects": "http://127.0.0.1:8770",
      "/idmap": "http://127.0.0.1:8770",
      "/ws": { target: "ws://127.0.0.1:8770", ws: true },
    },
  },
});
