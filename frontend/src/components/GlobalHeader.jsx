import { Link, useLocation } from 'react-router-dom';
import { User, Menu } from 'lucide-react';
import ThemeToggle from './ThemeToggle';

export default function GlobalHeader({ theme, onToggleTheme }) {
  const location = useLocation();
  const isLanding = location.pathname === '/';

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-ivory/90 backdrop-blur-md transition-colors duration-200 dark:bg-ink/90">
      <nav className="mx-auto flex w-full items-center justify-between px-6 py-6 lg:px-12 xl:px-16 2xl:px-24">
        {isLanding ? (
          <span className="pt-1 font-display text-4xl leading-none tracking-[0.14em]">JARVIS</span>
        ) : (
          <Link
            to="/"
            className="pt-1 font-display text-4xl leading-none tracking-[0.14em] cursor-pointer hover:text-teal-700 dark:hover:text-teal-400 transition-colors"
          >
            JARVIS
          </Link>
        )}

        <div className="flex items-center gap-6 lg:gap-8">
          <div className="hidden sm:flex items-center gap-6 text-sm font-serif">
            <Link
              to="/events"
              className={`transition-colors hover:text-teal-700 dark:hover:text-teal-400 ${
                location.pathname === '/events'
                  ? 'text-ink font-semibold dark:text-bone'
                  : 'text-muted'
              }`}
            >
              Listings
            </Link>
            <Link
              to="/submit"
              className={`transition-colors hover:text-teal-700 dark:hover:text-teal-400 ${
                location.pathname === '/submit'
                  ? 'text-ink font-semibold dark:text-bone'
                  : 'text-muted'
              }`}
            >
              Drop a Poster
            </Link>
          </div>

          <div className="flex items-center gap-4">
            <ThemeToggle theme={theme} onToggle={onToggleTheme} />
            
            <button
              type="button"
              aria-label="Your profile"
              className="grid size-11 cursor-pointer place-items-center rounded-full border border-line transition-colors hover:border-ink/40 focus-visible:outline-1 focus-visible:outline-offset-2 focus-visible:outline-teal-600 dark:hover:border-bone/40"
            >
              <User className="size-5" strokeWidth={1.25} />
            </button>
          </div>
        </div>
      </nav>
    </header>
  );
}

