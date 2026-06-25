/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // deeper, calmer base with subtle elevation steps (less flat grey)
        bg: "#0a0a0c", panel: "#101013", panel2: "#16161a",
        edge: "#1f1f25", edge2: "#2a2a31",
        txt: "#ededf2", muted: "#7d7d88", faint: "#55555f",
        accent: "#7c93ff", accent2: "#1e2436",
        good: "#3ecf8e", warn: "#e0a44a", risk: "#e0625c",
      },
      fontFamily: {
        sans: ["-apple-system","BlinkMacSystemFont","Segoe UI","Roboto","sans-serif"],
        mono: ["ui-monospace","SFMono-Regular","Menlo","monospace"],
      },
    },
  },
  plugins: [],
}
