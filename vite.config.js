import { resolve } from "node:path";
import { defineConfig } from "vite";

export default defineConfig({
  root: resolve("learning_app/static"),
  base: "/playground-assets/",
  optimizeDeps: { exclude: ["@electric-sql/pglite"] },
  worker: { format: "es" },
  build: {
    outDir: resolve("learning_app/dist"),
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: "[name].js",
        chunkFileNames: "chunks/[name]-[hash].js",
        assetFileNames: "[name][extname]",
      },
    },
  },
});
