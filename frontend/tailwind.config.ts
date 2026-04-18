import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: ['class'],
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    container: {
      center: true,
      padding: '2rem',
      screens: {
        '2xl': '1400px',
      },
    },
    extend: {
      fontFamily: {
        sans: ['var(--font-inter)', 'system-ui', 'sans-serif'],
        mono: ['var(--font-mono)', 'monospace'],
      },
      colors: {
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        success: {
          DEFAULT: 'hsl(var(--success))',
          foreground: 'hsl(var(--success-foreground))',
        },
        warning: {
          DEFAULT: 'hsl(var(--warning))',
          foreground: 'hsl(var(--warning-foreground))',
        },
        info: {
          DEFAULT: 'hsl(var(--info))',
          foreground: 'hsl(var(--info-foreground))',
        },
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        // Domain: state
        state: {
          draft: {
            DEFAULT: 'hsl(var(--state-draft))',
            foreground: 'hsl(var(--state-draft-foreground))',
          },
          'in-review': {
            DEFAULT: 'hsl(var(--state-in-review))',
            foreground: 'hsl(var(--state-in-review-foreground))',
          },
          ready: {
            DEFAULT: 'hsl(var(--state-ready))',
            foreground: 'hsl(var(--state-ready-foreground))',
          },
          blocked: {
            DEFAULT: 'hsl(var(--state-blocked))',
            foreground: 'hsl(var(--state-blocked-foreground))',
          },
          archived: {
            DEFAULT: 'hsl(var(--state-archived))',
            foreground: 'hsl(var(--state-archived-foreground))',
          },
          exported: {
            DEFAULT: 'hsl(var(--state-exported))',
            foreground: 'hsl(var(--state-exported-foreground))',
          },
        },
        // Domain: severity
        severity: {
          blocking: {
            DEFAULT: 'hsl(var(--severity-blocking))',
            foreground: 'hsl(var(--severity-blocking-foreground))',
          },
          warning: {
            DEFAULT: 'hsl(var(--severity-warning))',
            foreground: 'hsl(var(--severity-warning-foreground))',
          },
          info: {
            DEFAULT: 'hsl(var(--severity-info))',
            foreground: 'hsl(var(--severity-info-foreground))',
          },
        },
        // Domain: tier
        tier: {
          '1': {
            DEFAULT: 'hsl(var(--tier-1))',
            foreground: 'hsl(var(--tier-1-foreground))',
          },
          '2': {
            DEFAULT: 'hsl(var(--tier-2))',
            foreground: 'hsl(var(--tier-2-foreground))',
          },
          '3': {
            DEFAULT: 'hsl(var(--tier-3))',
            foreground: 'hsl(var(--tier-3-foreground))',
          },
          '4': {
            DEFAULT: 'hsl(var(--tier-4))',
            foreground: 'hsl(var(--tier-4-foreground))',
          },
        },
        // Domain: level (completeness)
        level: {
          low: {
            DEFAULT: 'hsl(var(--level-low))',
            foreground: 'hsl(var(--level-low-foreground))',
          },
          medium: {
            DEFAULT: 'hsl(var(--level-medium))',
            foreground: 'hsl(var(--level-medium-foreground))',
          },
          high: {
            DEFAULT: 'hsl(var(--level-high))',
            foreground: 'hsl(var(--level-high-foreground))',
          },
          ready: {
            DEFAULT: 'hsl(var(--level-ready))',
            foreground: 'hsl(var(--level-ready-foreground))',
          },
        },
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      keyframes: {
        'accordion-down': {
          from: { height: '0' },
          to: { height: 'var(--radix-accordion-content-height)' },
        },
        'accordion-up': {
          from: { height: 'var(--radix-accordion-content-height)' },
          to: { height: '0' },
        },
      },
      animation: {
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up': 'accordion-up 0.2s ease-out',
      },
      minHeight: {
        touch: '48px',
      },
      minWidth: {
        touch: '48px',
      },
    },
  },
  plugins: [],
};

export default config;
