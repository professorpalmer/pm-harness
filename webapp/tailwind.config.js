/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // lifted dark base with clear elevation steps (Hermes/Cursor-class
        // legibility: canvas is dark but not a void, each surface is visibly
        // lighter than the one below, secondary text stays readable).
        // Surfaces carry a faint cool blue-violet undertone (not pure neutral
        // grey) so the canvas has DEPTH instead of flat greyscale -- the Cursor/
        // Linear move. Each step stays a clear elevation above the one below.
        bg: "#16161c", panel: "#1f1f27", panel2: "#292932",
        edge: "#383844", edge2: "#494957",
        // Text keeps a hair of warmth so it doesn't read clinical on the cool base.
        txt: "#f5f4f8", muted: "#aaa9b8", faint: "#7e7d8d",
        // Accent: a slate-blue with a little more life than the fully-muted
        // version, but still nowhere near the old near-neon periwinkle. Reads as
        // "interactive + considered," not "vibe-coded."
        accent: "#8b96c4", accent2: "#23283a",
        // Status hues: present and legible, desaturated enough to stay
        // professional. Slightly richer than the washed-out pass.
        good: "#5fb98f", warn: "#cf9d56", risk: "#d4756d",
      },
      fontFamily: {
        sans: ["-apple-system","BlinkMacSystemFont","Segoe UI","Roboto","sans-serif"],
        mono: ["ui-monospace","SFMono-Regular","Menlo","monospace"],
      },
    },
  },
  plugins: [],
}
