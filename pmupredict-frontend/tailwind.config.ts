import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        turf: "#1B4332",
        "turf-dark": "#122E22",
        paper: "#F6F1E4",
        "paper-line": "#D9CFB8",
        ink: "#201A12",
        gold: "#B98C3D",
        silk: "#8C2F39",
        silver: "#8A8578",
        bronze: "#9C6B3E",
      },
      fontFamily: {
        display: ["var(--font-fraunces)", "serif"],
        body: ["var(--font-inter)", "sans-serif"],
        data: ["var(--font-plex-mono)", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
