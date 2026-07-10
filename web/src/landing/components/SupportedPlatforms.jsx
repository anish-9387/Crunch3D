const UnityIcon = () => (
  <svg viewBox="0 0 24 24" fill="currentColor" className="w-10 h-10">
    <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
  </svg>
)

const UnrealIcon = () => (
  <svg viewBox="0 0 24 24" fill="currentColor" className="w-10 h-10">
    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8z" />
    <path d="M12 6c-3.31 0-6 2.69-6 6s2.69 6 6 6 6-2.69 6-6-2.69-6-6-6zm0 10c-2.21 0-4-1.79-4-4s1.79-4 4-4 4 1.79 4 4-1.79 4-4 4z" />
  </svg>
)

const BlenderIcon = () => (
  <svg viewBox="0 0 24 24" fill="currentColor" className="w-10 h-10">
    <path d="M12 2.5a9.5 9.5 0 100 19 9.5 9.5 0 000-19zM12 18a6 6 0 110-12 6 6 0 010 12z" />
    <circle cx="12" cy="12" r="3" />
  </svg>
)

const WebGLIcon = () => (
  <svg viewBox="0 0 24 24" fill="currentColor" className="w-10 h-10">
    <path d="M21.5 6l-9.5-5.5-9.5 5.5v12l9.5 5.5 9.5-5.5v-12zM12 19L5 15V9l7 4v6zm1-7l7-4v6l-7 4v-6zm-1-8.5l7 4-7 4-7-4 7-4z" />
  </svg>
)

const OpenSourceIcon = () => (
  <svg viewBox="0 0 24 24" fill="currentColor" className="w-10 h-10">
    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" />
  </svg>
)

export default function SupportedPlatforms() {
  const platforms = [
    { name: 'Unity', icon: <UnityIcon /> },
    { name: 'Unreal Engine', icon: <UnrealIcon /> },
    { name: 'Blender', icon: <BlenderIcon /> },
    { name: 'WebGL', icon: <WebGLIcon /> },
    { name: 'Open Source', icon: <OpenSourceIcon /> },
  ]

  return (
    <section id="platforms" className="w-full py-16 flex flex-col items-center justify-center">
      <h3 className="text-sm font-semibold tracking-widest uppercase text-brand-muted mb-12">Supported Platforms</h3>

      <div className="flex flex-wrap justify-center gap-8 md:gap-16 w-full max-w-4xl">
        {platforms.map((platform, idx) => (
          <div
            key={idx}
            className="group flex flex-col items-center gap-4 text-brand-muted hover:text-brand-white transition-colors duration-300"
          >
            <div className="w-24 h-24 rounded-full bg-brand-dark border border-white/5 flex items-center justify-center group-hover:border-brand-white/20 group-hover:scale-110 transition-all duration-300 cursor-pointer shadow-lg shadow-black/50">
              {platform.icon}
            </div>
            <span className="text-sm font-medium tracking-wide">{platform.name}</span>
          </div>
        ))}
      </div>
    </section>
  )
}
