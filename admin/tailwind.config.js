/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          green: "#2E7D32",
          amber: "#FF8F00",
          brown: "#43362D",
        },
      },
    },
  },
  plugins: [],
};
