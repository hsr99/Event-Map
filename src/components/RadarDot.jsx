import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

const TONES = {
  teal: {
    core: 'bg-teal-600 shadow-[0_0_8px_2px_rgba(13,148,136,0.45)] dark:bg-teal-400 dark:shadow-[0_0_10px_2px_rgba(45,212,191,0.6)]',
    ring: 'border-teal-600/70 dark:border-teal-400/70',
  },
  gold: {
    core: 'bg-yellow-600 shadow-[0_0_8px_2px_rgba(202,138,4,0.45)] dark:bg-yellow-500 dark:shadow-[0_0_10px_2px_rgba(234,179,8,0.6)]',
    ring: 'border-yellow-600/70 dark:border-yellow-500/70',
  },
};

export default function RadarDot({ event, tone = 'teal', index = 0, interactive = false, onExplore }) {
  const styles = TONES[tone];
  const duration = 2.4 + (index % 3) * 0.5;
  const offset = index * 0.45;
  
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef(null);

  // Close tooltip if clicked outside (mobile tap handling)
  useEffect(() => {
    if (!interactive || !isOpen) return;

    function handleClickOutside(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('pointerdown', handleClickOutside);
    return () => document.removeEventListener('pointerdown', handleClickOutside);
  }, [interactive, isOpen]);

  return (
    <div
      ref={containerRef}
      className={`relative z-10 -translate-x-1/2 -translate-y-1/2 ${interactive ? 'cursor-pointer' : ''}`}
      onMouseEnter={() => interactive && setIsOpen(true)}
      onMouseLeave={() => interactive && setIsOpen(false)}
      onClick={() => interactive && setIsOpen(!isOpen)}
    >
      <motion.div
        initial={{ scale: 0, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ delay: 0.6 + index * 0.08, type: 'spring', stiffness: 260, damping: 18 }}
        className="relative grid size-8 place-items-center"
      >
        <div className="relative size-3">
          {[0, 1].map((ring) => (
            <motion.span
              key={ring}
              className={`absolute inset-0 rounded-full border ${styles.ring}`}
              initial={{ scale: 1, opacity: 0 }}
              animate={{ scale: [1, 5.5], opacity: [0.9, 0] }}
              transition={{
                duration,
                ease: 'easeOut',
                repeat: Infinity,
                delay: offset + ring * (duration / 2),
              }}
            />
          ))}
          <motion.span
            className={`absolute inset-0 rounded-full ${styles.core}`}
            animate={{ opacity: [1, 0.55, 1] }}
            transition={{ duration: duration / 1.5, repeat: Infinity, ease: 'easeInOut', delay: offset }}
          />
        </div>
      </motion.div>

      <AnimatePresence>
        {isOpen && interactive && (
          <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 5, scale: 0.95 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            // Tooltip positioning logic, we use dynamic classes or just let it overflow normally but we ensure z-index is high
            className="absolute bottom-full left-1/2 z-50 mb-3 -translate-x-1/2 w-48 border border-line bg-ivory/95 p-4 shadow-xl backdrop-blur-md dark:bg-ink/95"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="font-display text-xl leading-none text-ink dark:text-bone">{event.title}</h3>
            <p className="mt-1 text-xs italic text-muted">
              {event.area} · {event.date}
            </p>
            <button
              onClick={() => onExplore(event.id)}
              className="cursor-pointer group mt-3 flex w-full items-center justify-between text-xs font-semibold uppercase tracking-wider text-teal-700 transition-colors hover:text-teal-900 dark:text-teal-400 dark:hover:text-teal-200"
            >
              <span>Explore</span>
              <span className="transition-transform group-hover:translate-x-1">→</span>
            </button>
          </motion.div>
        )}
      </AnimatePresence>
      
      {/* Non-interactive static label for landing page */}
      {!interactive && (
        <span className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 translate-y-1 whitespace-nowrap border border-line bg-ivory/95 px-3 py-1.5 text-xs italic text-ink opacity-0 transition-all duration-300 group-hover:translate-y-0 group-hover:opacity-100 dark:bg-ink/95 dark:text-bone">
          {event.title} · {event.area}
        </span>
      )}
    </div>
  );
}

