import type { Config } from "tailwindcss";

export default {
  darkMode: ["class"],
  content: ["./pages/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./app/**/*.{ts,tsx}", "./src/**/*.{ts,tsx}"],
  prefix: "",
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        sidebar: {
          DEFAULT: "hsl(var(--sidebar-background))",
          foreground: "hsl(var(--sidebar-foreground))",
          primary: "hsl(var(--sidebar-primary))",
          "primary-foreground": "hsl(var(--sidebar-primary-foreground))",
          accent: "hsl(var(--sidebar-accent))",
          "accent-foreground": "hsl(var(--sidebar-accent-foreground))",
          border: "hsl(var(--sidebar-border))",
          ring: "hsl(var(--sidebar-ring))",
        },
        "voco-green": {
          DEFAULT: "#13F17D",
          50: "#E6FFF9",
          100: "#B3FFE6",
          200: "#80FFD3",
          300: "#4DFFC0",
          400: "#26F59E",
          500: "#13F17D",
          600: "#0DC86A",
          700: "#0D9B63",
          800: "#0A7A4F",
          900: "#0A2E1F",
        },
        "voco-cyan": {
          DEFAULT: "#00E5A0",
          50: "#E6FFF5",
          100: "#B3FFE0",
          200: "#80FFCB",
          300: "#4DFFB6",
          400: "#1AFFA1",
          500: "#00E5A0",
          600: "#00B880",
          700: "#008A60",
          800: "#005C40",
          900: "#002E20",
        },
        "voco-gradient": {
          from: "#13F17D",
          via: "#0DC86A",
          to: "#00E5A0",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      boxShadow: {
        "voco-glow": "0 0 15px rgba(19, 241, 125, 0.4)",
        "voco-glow-lg": "0 0 30px rgba(19, 241, 125, 0.5), 0 0 60px rgba(0, 229, 160, 0.2)",
        "voco-glow-sm": "0 0 8px rgba(19, 241, 125, 0.3)",
        "voco-glow-cyan": "0 0 15px rgba(0, 229, 160, 0.4)",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
        "orb-pulse": {
          "0%, 100%": { boxShadow: "0 0 20px rgba(19, 241, 125, 0.3), 0 0 60px rgba(0, 229, 160, 0.1)" },
          "50%": { boxShadow: "0 0 40px rgba(19, 241, 125, 0.5), 0 0 80px rgba(0, 229, 160, 0.2)" },
        },
        "orb-listening": {
          "0%, 100%": { transform: "scale(1)", boxShadow: "0 0 30px rgba(19, 241, 125, 0.4)" },
          "50%": { transform: "scale(1.05)", boxShadow: "0 0 50px rgba(19, 241, 125, 0.6), 0 0 100px rgba(0, 229, 160, 0.2)" },
        },
        // Progress-bar slide for async background job nodes
        "progress-slide": {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(300%)" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        "orb-pulse": "orb-pulse 3s ease-in-out infinite",
        "orb-listening": "orb-listening 1.5s ease-in-out infinite",
        "progress-slide": "progress-slide 2s ease-in-out infinite",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
} satisfies Config;
