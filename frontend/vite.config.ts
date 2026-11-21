// frontend/vite.config.ts
import { defineConfig } from "vite";

// Build straight into the backend so one container serves everything.
export default defineConfig({
  build: { outDir: "../backend/static", emptyOutDir: true },
  server: { host: "0.0.0.0", proxy: { "/ws": { target: "ws://127.0.0.1:8670", ws: true } } },
});
