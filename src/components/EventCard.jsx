import { motion } from 'framer-motion';
import EventImage from './EventImage';
import { formatDate, formatPrice, formatTime } from '../lib/format';

export default function EventCard({ event, onSelect, ref }) {
  return (
    <motion.article
      ref={ref}
      layout
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.94, transition: { duration: 0.2 } }}
      transition={{ type: 'spring', stiffness: 320, damping: 32 }}
      className="group relative flex flex-col border border-line transition-colors duration-500 hover:border-ink/30 has-[:focus-visible]:border-teal-600 dark:hover:border-bone/30 dark:has-[:focus-visible]:border-teal-400"
    >
      <EventImage
        event={event}
        className="aspect-[4/3]"
        imgClassName="saturate-[0.85] transition-[scale,filter] duration-[1200ms] ease-[cubic-bezier(0.22,1,0.36,1)] group-hover:scale-105 group-hover:saturate-100"
      />

      <div className="flex flex-1 flex-col p-5 sm:p-6">
        <p className="flex items-center gap-3 text-[11px] uppercase tracking-[0.22em] text-muted">
          <span className="text-teal-700 dark:text-teal-400">{event.category}</span>
          <span aria-hidden className="h-px w-5 bg-current opacity-40" />
          <span>{event.area}</span>
        </p>

        <h3 className="mt-3 font-display text-[2rem] leading-[0.95] tracking-[0.02em]">
          {/* The ::before overlay stretches the click target across the whole card while keeping one real button */}
          <button
            type="button"
            onClick={() => onSelect(event)}
            className="cursor-pointer text-left outline-none before:absolute before:inset-0"
          >
            {event.title}
          </button>
        </h3>

        <div className="mt-auto pt-6">
          <div className="flex items-baseline justify-between gap-4 border-t border-line pt-4 text-sm">
            <time dateTime={event.date} className="italic text-muted">
              {formatDate(event.date)} · {formatTime(event.date)}
            </time>
            <span className={event.isFree ? 'text-teal-700 dark:text-teal-400' : 'text-yellow-700 dark:text-yellow-500'}>
              {formatPrice(event)}
            </span>
          </div>
        </div>
      </div>
    </motion.article>
  );
}
