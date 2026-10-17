import { defineConfig } from "vite";

// src/ds -> design/dist/bundle.js: one classic script that sets window.ToneMatch, using the page's
// window.React / window.ReactDOM (the design-system artifact's previews load React 18 themselves).
export default defineConfig({
  publicDir: false,
  build: {
    outDir: "design/dist",
    emptyOutDir: true,
    minify: false,
    lib: { entry: "src/ds/index.ts", name: "ToneMatch", formats: ["iife"], fileName: () => "bundle.js" },
    rollupOptions: { external: ["react", "react-dom"], output: { globals: { react: "React", "react-dom": "ReactDOM" } } },
  },
});
