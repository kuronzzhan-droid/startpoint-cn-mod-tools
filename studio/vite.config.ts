import { defineConfig } from "vite";

// Backend: python -m wf.studio (127.0.0.1:8790). `npm run dev` proxies /api to it.
export default defineConfig({
  esbuild: { jsx: "automatic", jsxImportSource: "preact" },
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8790" } },
  build: { outDir: "dist", emptyOutDir: true, chunkSizeWarningLimit: 600 },
});
