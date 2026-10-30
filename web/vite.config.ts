/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In development the FastAPI app runs on 8000: `uv run uvicorn openenergy.app:app`.
const backend = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": backend,
      "/download": backend,
      "/battery": backend,
      "/health": backend,
    },
  },
  // plotly (about 1.2 MB) is its own chunk, loaded only by pages with charts.
  build: { outDir: "dist", emptyOutDir: true, chunkSizeWarningLimit: 1300 },
  test: { environment: "jsdom", include: ["src/**/*.test.{ts,tsx}"] },
});
