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
        paper: {
          bg: "#F6F7F4",
          surface: "#FFFFFF",
          ink: "#202A2E",
          slate: "#687277",
          border: "#DDE2E0",
          accent: "#287C78",
          "accent-light": "#E2F0EE",
          "accent-dark": "#1E625F",
        },
        rel: {
          corroborated: {
            bg: "#E2F0EE",
            fg: "#286B67",
            icon: "#287C78",
            border: "#BEE3E0",
          },
          contradiction: {
            bg: "#F4E6E2",
            fg: "#92564E",
            icon: "#A96359",
            border: "#E8CECA",
          },
          reconciled: {
            bg: "#F4EDDC",
            fg: "#896D35",
            icon: "#A88343",
            border: "#E7D8B9",
          },
          uncertain: {
            bg: "#E9EDF0",
            fg: "#65727A",
            icon: "#71808A",
            border: "#D2D9DE",
          },
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "sans-serif"],
        serif: ["var(--font-source-serif)", "serif"],
      },
    },
  },
  plugins: [],
};

export default config;
