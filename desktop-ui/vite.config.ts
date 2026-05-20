import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: {
    port: 1420,
    strictPort: true,
    proxy: {
      "/chat": { target: "http://localhost:19198", changeOrigin: true },
      "/status": { target: "http://localhost:19198", changeOrigin: true },
      "/models": { target: "http://localhost:19198", changeOrigin: true },
      "/model": { target: "http://localhost:19198", changeOrigin: true },
      "/config": { target: "http://localhost:19198", changeOrigin: true },
      "/mastery": { target: "http://localhost:19198", changeOrigin: true },
      "/reset": { target: "http://localhost:19198", changeOrigin: true },
      "/agents": { target: "http://localhost:19198", changeOrigin: true },
      "/report": { target: "http://localhost:19198", changeOrigin: true },
      "/api": { target: "http://localhost:19198", changeOrigin: true },
    },
  },
  build: { outDir: "dist", emptyOutDir: true },
});
