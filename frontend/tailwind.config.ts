import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './app/**/*.{ts,tsx}',
    './src/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Vazirmatn', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['Fira Code', 'Monaco', 'Cascadia Code', 'Consolas', 'monospace'],
      },
      colors: {
        /* ZarinPal brand color aliases — usable as Tailwind utilities */
        'zarin-green':       '#36B37E',
        'zarin-green-light': '#48C990',
        'zarin-green-dark':  '#2A9065',
        'zarin-green-muted': '#1D6347',
        'zarin-navy':        '#0D1B4B',
        'zarin-navy-soft':   '#1A2F6B',
        'zarin-navy-muted':  '#263D7A',
        'zarin-navy-faint':  '#E8EBF6',
        'zarin-gold':        '#F5A623',
        'zarin-gold-light':  '#FFBB44',
        'zarin-gold-dark':   '#C8841B',
        'zarin-gold-muted':  '#7A5210',
        'gold':              '#F5A623',
        'gold-light':        '#FFBB44',
        'gold-dark':         '#C8841B',
        'gold-deep':         '#C8841B',
        'gold-muted':        '#7A5210',
        'leaf':              '#36B37E',
        'leaf-light':        '#48C990',
        'leaf-dark':         '#2A9065',
        'leaf-muted':        '#1D6347',
        'royal':             '#0D1B4B',
        'royal-soft':        '#1A2F6B',
        'royal-muted':       '#263D7A',
        'royal-faint':       '#E8EBF6',
      },
    },
  },
  plugins: [],
}

export default config
