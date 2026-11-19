import { NavLink } from 'react-router-dom';
import { Home, LayoutGrid, UploadCloud } from 'lucide-react';

const TABS = [
  { to: '/', label: 'Home', icon: Home, end: true },
  { to: '/events', label: 'Listings', icon: LayoutGrid },
  { to: '/submit', label: 'Drop a Poster', icon: UploadCloud },
];

// Bottom navigation for phones. The header's text links are hidden below `sm`,
// so this is how mobile visitors move between pages.
export default function MobileTabBar() {
  return (
    <nav
      aria-label="Main"
      className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-ivory/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-md transition-colors duration-200 sm:hidden dark:bg-ink/95"
    >
      <ul className="grid grid-cols-3">
        {TABS.map(({ to, label, icon: Icon, end }) => (
          <li key={to}>
            <NavLink
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex h-16 flex-col items-center justify-center gap-1 text-[11px] font-serif tracking-wide transition-colors ${
                  isActive ? 'text-teal-700 dark:text-teal-400' : 'text-muted'
                }`
              }
            >
              <Icon className="size-5" strokeWidth={1.5} />
              <span>{label}</span>
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
