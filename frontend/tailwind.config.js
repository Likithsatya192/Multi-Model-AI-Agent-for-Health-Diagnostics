/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./app/**/*.{js,ts,jsx,tsx,mdx}",
        "./components/**/*.{js,ts,jsx,tsx,mdx}",
        "./lib/**/*.{js,ts,jsx,tsx,mdx}",
    ],
    theme: {
        extend: {
            colors: {
                // Core surfaces — deep navy-black medical monitor palette
                background:       "#07090f",   // near-black with blue tint
                surface:          "#0f1623",   // deep navy surface
                surfaceHighlight: "#1a2540",   // elevated surface

                // Brand — electric cyan (medical scanner)
                primary:     "#0EA5E9",        // sky-500
                primaryDark: "#0284C7",        // sky-600
                primaryGlow: "#38BDF8",        // sky-400 (glow variant)

                // Accent — bioluminescent teal
                accent:      "#06D6A0",        // teal-green (health)
                accentDark:  "#059669",

                // Semantic
                secondary: "#94A3B8",          // slate-400
                success:   "#22c55e",
                error:     "#ef4444",
                warning:   "#f59e0b",

                // Chart colours
                chartNormal: "#22c55e",
                chartLow:    "#eab308",
                chartHigh:   "#ef4444",
            },

            fontFamily: {
                sans:    ['Plus Jakarta Sans', 'ui-sans-serif', 'system-ui', 'sans-serif'],
                display: ['Plus Jakarta Sans', 'ui-sans-serif', 'system-ui', 'sans-serif'],
                mono:    ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'monospace'],
            },

            borderColor: {
                DEFAULT: "rgba(255,255,255,0.07)",
            },

            animation: {
                'fade-in':      'fadeIn 0.5s ease-out both',
                'slide-up':     'slideUp 0.5s ease-out both',
                'slide-right':  'slideRight 0.4s ease-out both',
                'pulse-slow':   'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                'shimmer':      'shimmer 2s infinite',
                'glow-pulse':   'glowPulse 4s ease-in-out infinite',
                'cell-float':   'cellFloat 8s ease-in-out infinite',
                'cell-float-2': 'cellFloat2 10s ease-in-out infinite',
                'data-stream':  'dataStream 0.4s ease-out both',
                'rotate-slow':  'rotateSlow 20s linear infinite',
                'ecg-trace':    'ecgTrace 5s cubic-bezier(0.4,0,0.2,1) infinite',
                'scan-sweep':   'scanSweep 6s ease-in-out infinite',
                'count-up':     'countUp 0.6s ease-out both',
            },

            keyframes: {
                fadeIn: {
                    from: { opacity: '0' },
                    to:   { opacity: '1' },
                },
                slideUp: {
                    from: { transform: 'translateY(20px)', opacity: '0' },
                    to:   { transform: 'translateY(0)',    opacity: '1' },
                },
                slideRight: {
                    from: { transform: 'translateX(-16px)', opacity: '0' },
                    to:   { transform: 'translateX(0)',     opacity: '1' },
                },
                shimmer: {
                    '0%':   { backgroundPosition: '-200% 0' },
                    '100%': { backgroundPosition:  '200% 0' },
                },
                glowPulse: {
                    '0%, 100%': { opacity: '0.4', filter: 'blur(60px)' },
                    '50%':      { opacity: '0.7', filter: 'blur(80px)' },
                },
                cellFloat: {
                    '0%, 100%': { transform: 'translateY(0px) rotate(0deg) scale(1)',     opacity: '0.15' },
                    '33%':      { transform: 'translateY(-18px) rotate(120deg) scale(1.05)', opacity: '0.25' },
                    '66%':      { transform: 'translateY(-8px) rotate(240deg) scale(0.95)',  opacity: '0.2' },
                },
                cellFloat2: {
                    '0%, 100%': { transform: 'translateY(0px) translateX(0px) scale(1)',      opacity: '0.1' },
                    '50%':      { transform: 'translateY(-24px) translateX(8px) scale(1.1)',   opacity: '0.2' },
                },
                dataStream: {
                    from: { transform: 'translateY(8px)', opacity: '0' },
                    to:   { transform: 'translateY(0)',   opacity: '1' },
                },
                rotateSlow: {
                    from: { transform: 'rotate(0deg)' },
                    to:   { transform: 'rotate(360deg)' },
                },
                ecgTrace: {
                    '0%':   { strokeDashoffset: '2400', opacity: '0' },
                    '5%':   { opacity: '1' },
                    '85%':  { opacity: '0.8' },
                    '100%': { strokeDashoffset: '-2400', opacity: '0' },
                },
                countUp: {
                    from: { transform: 'translateY(6px)', opacity: '0' },
                    to:   { transform: 'translateY(0)',   opacity: '1' },
                },
            },

            opacity: {
                '8':  '0.08',
                '15': '0.15',
                '35': '0.35',
                '45': '0.45',
                '55': '0.55',
                '65': '0.65',
                '85': '0.85',
                '95': '0.95',
            },

        spacing: {
                '4.5': '1.125rem',
                '5.5': '1.375rem',
                '18':  '4.5rem',
            },

            maxWidth: {
                '8xl': '88rem',
            },

            boxShadow: {
                'primary-sm': '0 2px 12px rgba(14,165,233,0.2)',
                'primary-md': '0 4px 24px rgba(14,165,233,0.3)',
                'primary-lg': '0 8px 40px rgba(14,165,233,0.35)',
                'glow-sm':    '0 0 20px rgba(14,165,233,0.25)',
                'glow-md':    '0 0 40px rgba(14,165,233,0.3)',
                'inner-glow': 'inset 0 1px 0 rgba(255,255,255,0.07)',
            },

            backdropBlur: {
                'xs': '2px',
                '2xl': '40px',
                '3xl': '64px',
            },
        },
    },
    plugins: [],
};
