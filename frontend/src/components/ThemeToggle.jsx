import { AnimatePresence, motion } from 'framer-motion';
import { Moon, Sun } from 'lucide-react';

export default function ThemeToggle({ theme, onToggle, className = '' }) {
  const isDark = theme === 'dark';
  const label = `Switch to ${isDark ? 'light' : 'dark'} mode`;

  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label={label}
      title={label}
      className={`cursor-pointer grid size-11 place-items-center overflow-hidden border border-line text-ink transition-colors duration-300 hover:border-teal-700 hover:text-teal-700 focus-visible:outline-1 focus-visible:outline-offset-2 focus-visible:outline-teal-600 dark:text-bone dark:hover:border-teal-400 dark:hover:text-teal-400 ${className}`}
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={theme}
          initial={{ y: 14, opacity: 0, rotate: -45 }}
          animate={{ y: 0, opacity: 1, rotate: 0 }}
          exit={{ y: -14, opacity: 0, rotate: 45 }}
          transition={{ duration: 0.25 }}
        >
          {isDark ? <Sun className="size-5" strokeWidth={1.25} /> : <Moon className="size-5" strokeWidth={1.25} />}
        </motion.span>
      </AnimatePresence>
    </button>
  );
}
