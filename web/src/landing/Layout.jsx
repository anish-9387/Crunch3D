import Navbar from './components/Navbar'

export default function Layout({ children, onTryDemo }) {
  return (
    <div className="w-full min-h-screen bg-brand-black text-brand-white selection:bg-brand-red/30">
      <div className="max-w-[1400px] mx-auto px-6 py-6 md:py-8 flex flex-col gap-8 md:gap-14 lg:gap-16">
        <Navbar onTryDemo={onTryDemo} />

        <main className="flex flex-col flex-1 justify-center gap-12 lg:gap-16">{children}</main>

        <footer className="w-full border-t border-white/10 pt-8 pb-12 flex justify-between text-sm text-brand-muted">
          <p>© 2026 Crunch3d. Open-source 3D optimization.</p>
          <div className="flex gap-4">
            <a href="#" className="hover:text-brand-white">
              GitHub
            </a>
            <a href="#" className="hover:text-brand-white">
              Twitter
            </a>
          </div>
        </footer>
      </div>
    </div>
  )
}
