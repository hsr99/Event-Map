import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { ArrowRight, Check, X } from 'lucide-react';
import EventImage from './EventImage';
import { formatLongDate, formatPrice, formatTimeRange } from '../lib/format';

const EASE = [0.32, 0.72, 0, 1];

export default function EventDrawer({ event, onClose }) {
  const [reserved, setReserved] = useState(false);
  const priceTone = event.isFree ? 'text-teal-700 dark:text-teal-400' : 'text-yellow-700 dark:text-yellow-500';

  useEffect(() => {
    const onKeyDown = (e) => e.key === 'Escape' && onClose();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [onClose]);

  const details = [
    ['Venue', event.venue],
    ['Neighbourhood', event.area],
    ['Date', formatLongDate(event.date)],
    ['Timings', formatTimeRange(event.date, event.end_date)],
    ['Admission', event.isFree ? 'Free entry, registration required' : `${formatPrice(event)} per guest`],
  ];

  return (
    <>
      <motion.div
        aria-hidden
        onClick={onClose}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.35 }}
        className="fixed inset-0 z-40 bg-ink/60 backdrop-blur-[2px]"
      />

      <motion.aside
        role="dialog"
        aria-modal="true"
        aria-labelledby="event-drawer-title"
        initial={{ x: '100%' }}
        animate={{ x: 0 }}
        exit={{ x: '100%' }}
        transition={{ duration: 0.55, ease: EASE }}
        className="fixed inset-y-0 right-0 z-50 flex w-full max-w-xl flex-col border-l border-line bg-ivory text-ink transition-colors duration-200 dark:bg-ink dark:text-bone"
      >
        <div className="flex items-center justify-between border-b border-line px-6 py-4 sm:px-10">
          <p className="text-[11px] uppercase tracking-[0.3em] text-muted">Event details</p>
          <button
            type="button"
            onClick={onClose}
            autoFocus
            aria-label="Close details"
            className="cursor-pointer grid size-9 place-items-center border border-line transition-colors hover:border-ink/40 focus-visible:outline-1 focus-visible:outline-offset-2 focus-visible:outline-teal-600 dark:hover:border-bone/40"
          >
            <X className="size-4" strokeWidth={1.25} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          <EventImage event={event} className="aspect-[16/10]" />

          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.5, ease: EASE }}
            className="px-6 pb-10 pt-8 sm:px-10"
          >
            <p className="flex items-center gap-3 text-[11px] uppercase tracking-[0.22em] text-muted">
              <span className="text-teal-700 dark:text-teal-400">{event.category}</span>
              <span aria-hidden className="h-px w-5 bg-current opacity-40" />
              <span>{event.area}</span>
            </p>
            <h2
              id="event-drawer-title"
              className="mt-4 font-display text-5xl leading-[0.9] tracking-[0.02em] sm:text-6xl"
            >
              {event.title}
            </h2>
            <p className="mt-6 text-lg leading-relaxed text-ink/75 dark:text-bone/75">{event.description}</p>

            <dl className="mt-10 border-t border-line">
              {details.map(([term, value]) => (
                <div key={term} className="grid grid-cols-[8.5rem_1fr] gap-4 border-b border-line py-4 text-sm">
                  <dt className="italic text-muted">{term}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
          </motion.div>
        </div>

        <div className="flex items-center justify-between gap-6 border-t border-line px-6 py-5 sm:px-10">
          <div>
            <p className="text-xs italic text-muted">{event.isFree ? 'Admission' : 'Per guest'}</p>
            <p className={`mt-1 font-display text-4xl leading-none ${priceTone}`}>{formatPrice(event)}</p>
          </div>
          <button
            type="button"
            disabled={reserved}
            onClick={() => setReserved(true)}
            className="cursor-pointer group inline-flex items-center gap-4 bg-ink px-7 pb-3.5 pt-4 font-display text-xl tracking-[0.14em] text-ivory transition-colors duration-300 hover:bg-teal-700 focus-visible:outline-1 focus-visible:outline-offset-4 focus-visible:outline-teal-600 disabled:cursor-default disabled:bg-teal-700 dark:bg-bone dark:text-ink dark:hover:bg-teal-400 dark:disabled:bg-teal-400"
          >
            {reserved ? (
              <>
                <Check className="-mt-1 size-4" strokeWidth={1.5} />
                Request received
              </>
            ) : (
              <>
                {event.isFree ? 'Reserve Seat' : 'Book Tickets'}
                <ArrowRight
                  className="-mt-1 size-4 transition-transform duration-300 group-hover:translate-x-1"
                  strokeWidth={1.5}
                />
              </>
            )}
          </button>
        </div>
      </motion.aside>
    </>
  );
}
