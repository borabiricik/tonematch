import { defineConfig } from "vite";

// Tauri expects a fixed dev port and must not watch the Rust side.
export default defineConfig({
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    watch: { ignored: ["**/src-tauri/**"] },
  },
  // three.js (the 3D tuner) is its own lazy chunk of ~600 kB; it only loads on the Tuner page
  build: { target: "es2022", outDir: "dist", chunkSizeWarningLimit: 700 },
});
