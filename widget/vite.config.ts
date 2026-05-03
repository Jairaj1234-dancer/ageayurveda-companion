import { defineConfig } from "vite";
import { resolve } from "path";

export default defineConfig({
  build: {
    lib: {
      entry: resolve(__dirname, "src/index.ts"),
      name: "AgeAyurvedaWidget",
      formats: ["iife"],
      fileName: () => "ageayurveda-widget.js",
    },
    outDir: "dist",
    cssCodeSplit: false,
    minify: "esbuild",
    rollupOptions: {
      output: {
        inlineDynamicImports: true,
      },
    },
  },
});
