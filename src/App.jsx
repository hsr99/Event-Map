import { useEffect, useState } from 'react';
import { AnimatePresence, MotionConfig } from 'framer-motion';
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import GlobalHeader from './components/GlobalHeader';
import LandingView from './views/LandingView';
import CategoryHub from './views/CategoryHub';
import EventGridView from './views/EventGridView';

const THEME_KEY = 'jarvis-theme';

// An animated wrapper for our routes
function AnimatedRoutes({ theme, toggleTheme }) {
  const location = useLocation();

  return (
    <AnimatePresence mode="wait" onExitComplete={() => window.scrollTo(0, 0)}>
      <Routes location={location} key={location.pathname}>
        <Route
          path="/"
          element={<LandingView theme={theme} onToggleTheme={toggleTheme} />}
        />
        <Route
          path="/events"
          element={<CategoryHub theme={theme} onToggleTheme={toggleTheme} />}
        />
        <Route
          path="/events/:categoryId"
          element={<EventGridView theme={theme} onToggleTheme={toggleTheme} />}
        />
      </Routes>
    </AnimatePresence>
  );
}

export default function App() {
  const [theme, setTheme] = useState(() =>
    document.documentElement.classList.contains('dark') ? 'dark' : 'light',
  );

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch {
      /* storage unavailable */
    }
  }, [theme]);

  const toggleTheme = () => setTheme((current) => (current === 'dark' ? 'light' : 'dark'));

  return (
    <BrowserRouter>
      <MotionConfig reducedMotion="user">
        <div className="flex min-h-svh flex-col overflow-x-clip bg-ivory text-ink transition-colors duration-200 dark:bg-ink dark:text-bone">
          <GlobalHeader theme={theme} onToggleTheme={toggleTheme} />
          <div className="flex-1">
            <AnimatedRoutes theme={theme} toggleTheme={toggleTheme} />
          </div>
        </div>
      </MotionConfig>
    </BrowserRouter>
  );
}
