import { motion } from 'framer-motion';

const TONES = {
  teal: 'bg-teal-700 dark:bg-teal-400',
  gold: 'bg-yellow-600 dark:bg-yellow-500',
};

export default function UnderlineTab({ label, count, active, onClick, group, tone = 'teal', className = '' }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`cursor-pointer relative shrink-0 pb-2 pt-1 transition-colors duration-300 focus-visible:outline-1 focus-visible:outline-offset-4 focus-visible:outline-teal-600 ${
        active ? 'text-ink dark:text-bone' : 'text-muted hover:text-ink dark:hover:text-bone'
      } ${className}`}
    >
      {label}
      {count !== undefined && <sup className="ml-1 text-[10px] tabular-nums opacity-60">{count}</sup>}
      {/* layoutId is namespaced per group so each underline slides only within its own tab row */}
      {active && (
        <motion.span
          layoutId={`underline-${group}`}
          className={`absolute inset-x-0 bottom-0 h-[1.5px] ${TONES[tone]}`}
          transition={{ type: 'spring', bounce: 0.15, duration: 0.5 }}
        />
      )}
    </button>
  );
}
