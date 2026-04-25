import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/snapshot": { target: "http://localhost:8000", changeOrigin: true },
      "/sentiment": { target: "http://localhost:8000", changeOrigin: true },
      "/health": { target: "http://localhost:8000", changeOrigin: true },
      "/news": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
