/** @type {import('tailwindcss').Config} */
function withOpacity(rgbVar) {
  return `rgb(var(${rgbVar}) / <alpha-value>)`;
}

export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: ["selector", '[data-theme="dark"]'],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Estedad", "Inter", "system-ui", "sans-serif"],
      },
      colors: {
        bg: withOpacity("--c-bg-rgb"),
        surface: withOpacity("--c-surface-rgb"),
        "surface-2": withOpacity("--c-surface-2-rgb"),
        text: withOpacity("--c-text-rgb"),
        muted: withOpacity("--c-text-muted-rgb"),
        primary: {
          DEFAULT: withOpacity("--c-primary-rgb"),
          strong: withOpacity("--c-primary-strong-rgb"),
        },
        "primary-text": withOpacity("--c-primary-text-rgb"),
        accent: withOpacity("--c-accent-rgb"),
        success: withOpacity("--c-success-rgb"),
        warning: withOpacity("--c-warning-rgb"),
        danger: withOpacity("--c-danger-rgb"),
        // NOTE: unlike every other color above, this has a fixed baked-in alpha instead of
        // Tailwind's <alpha-value> placeholder — an opacity modifier (e.g. border-border/60)
        // REPLACES that alpha instead of multiplying it, so never suffix this token with /NN.
        border: "rgb(var(--c-border-rgb) / var(--c-border-alpha))",
        overlay: "rgb(var(--c-overlay-rgb) / var(--c-overlay-alpha))",
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
        full: "var(--radius-full)",
      },
      boxShadow: {
        sm: "var(--shadow-sm)",
        md: "var(--shadow-md)",
        lg: "var(--shadow-lg)",
      },
      keyframes: {
        "shimmer-slide": {
          to: { transform: "translate(calc(100cqw - 100%), 0)" },
        },
        "spin-around": {
          "0%": { transform: "translateZ(0) rotate(0deg)" },
          "15%, 35%": { transform: "translateZ(0) rotate(90deg)" },
          "65%, 85%": { transform: "translateZ(0) rotate(270deg)" },
          "100%": { transform: "translateZ(0) rotate(360deg)" },
        },
      },
      animation: {
        "shimmer-slide": "shimmer-slide var(--speed,3s) ease-in-out infinite alternate",
        "spin-around": "spin-around calc(var(--speed,3s)*2) infinite linear",
      },
    },
  },
  plugins: [],
};
