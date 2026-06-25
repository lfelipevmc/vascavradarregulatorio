import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // VCW brand colors
        navy: {
          50: "#eff6ff",
          100: "#dbeafe",
          200: "#bfdbfe",
          300: "#93c5fd",
          400: "#60a5fa",
          500: "#3b82f6",
          600: "#1d4ed8",
          700: "#1e3a8a",
          800: "#1a2f6b",
          900: "#0f1f4a",
          950: "#0a1530",
        },
        gold: {
          50: "#fefce8",
          100: "#fef9c3",
          200: "#fef08a",
          300: "#fde047",
          400: "#facc15",
          500: "#d4a017",
          600: "#b8860b",
          700: "#92690a",
          800: "#78520c",
          900: "#633d0e",
        },
        brand: {
          primary: "#0f1f4a",   // deep navy
          secondary: "#1a2f6b", // mid navy
          accent: "#d4a017",    // gold
          light: "#e8f0fe",     // light blue
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      boxShadow: {
        card: "0 1px 3px 0 rgba(15, 31, 74, 0.1), 0 1px 2px -1px rgba(15, 31, 74, 0.1)",
        "card-hover": "0 4px 6px -1px rgba(15, 31, 74, 0.1), 0 2px 4px -2px rgba(15, 31, 74, 0.1)",
      },
    },
  },
  plugins: [],
};

export default config;
