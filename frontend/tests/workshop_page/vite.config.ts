// frontend/tests/workshop_page/vite.config.ts - builds the harness into /tmp (not into backend/static)
import { defineConfig } from "vite";

export default defineConfig({ root: __dirname, build: { outDir: "/tmp/friday-ws-page", emptyOutDir: true } });
