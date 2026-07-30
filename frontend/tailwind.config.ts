import type { Config } from "tailwindcss";

// Design tokens follow the visual direction from the reference mockup —
// dark surface hierarchy, indigo/teal accent pair — refined with a
// slightly wider surface scale and proper semantic naming so components
// don't reach for raw hex values.
const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {

      colors: {
        bg: "var(--color-bg)",
        surface: {
          DEFAULT: "var(--color-surface)",
          2: "var(--color-surface-2)",
          3: "var(--color-surface-3)",
        },
        border: {
          DEFAULT: "var(--color-border)",
          2: "var(--color-border-2)",
        },
        accent: {
          DEFAULT: "var(--color-accent)",
          light: "var(--color-accent-light)",
          dim: "var(--color-accent-dim)",
        },
        teal: {
          DEFAULT: "var(--color-teal)",
          dim: "var(--color-teal-dim)",
        },
        amber: {
          DEFAULT: "var(--color-amber)",
          dim: "var(--color-amber-dim)",
        },
        danger: {
          DEFAULT: "var(--color-danger)",
          dim: "var(--color-danger-dim)",
        },
        info: {
          DEFAULT: "var(--color-info)",
          dim: "var(--color-info-dim)",
        },
        purple: {
          DEFAULT: "var(--color-purple)",
          dim: "var(--color-purple-dim)",
        },
        ink: {
          DEFAULT: "var(--color-ink)",
          2: "var(--color-ink-2)",
          3: "var(--color-ink-3)",
        },
      },

      fontFamily: {
        sans: ["var(--font-inter)", "sans-serif"],
        mono: ["var(--font-jetbrains-mono)", "monospace"],
      },
      borderRadius: {
        card: "12px",
      },
      boxShadow: {
        glow: "0 4px 12px rgba(91,95,239,.35)",
      },
    },
  },
  plugins: [],
};
export default config;
