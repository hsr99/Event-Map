import { motion } from 'framer-motion';
import { X } from 'lucide-react';

const CATEGORIES = [
  { id: 'all', title: 'All Experiences', subtitle: 'Browse everything', colSpan: 'col-span-1 md:col-span-3', bg: 'bg-gradient-to-r from-ink to-neutral-800 dark:from-bone dark:to-neutral-200 text-bone dark:text-ink', isAll: true },
  { id: 'college-culturals', title: 'College Culturals', subtitle: 'The biggest student-run fests in the city', colSpan: 'col-span-1 md:col-span-2', bg: 'bg-gradient-to-br from-teal-900/40 to-ink dark:from-teal-900/20 dark:to-ink' },
  { id: 'tech-events', title: 'Tech Events', subtitle: 'Hackathons, summits & builder meetups', colSpan: 'col-span-1', bg: 'bg-gradient-to-bl from-neutral-200 to-ivory dark:from-neutral-800 dark:to-ink' },
  { id: 'movies', title: 'Movies', subtitle: 'Indie screenings & retrospectives', colSpan: 'col-span-1', bg: 'bg-neutral-100 dark:bg-neutral-900' },
  { id: 'concerts', title: 'Concerts', subtitle: 'Live music, indie gigs & electronic nights', colSpan: 'col-span-1 md:col-span-2', bg: 'bg-gradient-to-tr from-yellow-700/20 to-ivory dark:from-yellow-900/20 dark:to-ink' },
  { id: 'social-gatherings', title: 'Social Gatherings', subtitle: 'Food walks, supper clubs & heritage tours', colSpan: 'col-span-1 md:col-span-3', bg: 'bg-gradient-to-r from-stone-200 to-ivory dark:from-stone-900 dark:to-ink' },
];

const container = {
  hidden: { opacity: 0, scale: 1.05 },
  show: { opacity: 1, scale: 1, transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1], staggerChildren: 0.08, delayChildren: 0.1 } },
  exit: { opacity: 0, scale: 1.02, transition: { duration: 0.3, ease: 'easeIn' } },
};

const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1] } },
};

export default function CategoryBentoOverlay({ onSelectCategory, onClose }) {
  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="show"
      exit="exit"
      className="fixed inset-0 z-50 overflow-y-auto bg-neutral-50/80 backdrop-blur-xl dark:bg-neutral-950/80 px-6 py-12 lg:px-12 xl:px-16 2xl:px-24"
    >
      <div className="mx-auto max-w-6xl">
        <div className="flex items-center justify-between pb-8">
          <motion.h2 variants={item} className="font-display text-4xl tracking-wide text-ink dark:text-bone">
            Directory
          </motion.h2>
          <motion.button
            variants={item}
            onClick={onClose}
            className="group flex cursor-pointer items-center gap-2 text-sm uppercase tracking-widest text-muted transition-colors hover:text-ink dark:hover:text-bone"
          >
            Close
            <X className="h-5 w-5 transition-transform group-hover:rotate-90" strokeWidth={1.5} />
          </motion.button>
        </div>

        <motion.div variants={item} className="grid grid-cols-1 gap-6 md:grid-cols-3">
          {CATEGORIES.map((cat) => {
            // Determine text colors based on whether it's the "All" category which overrides bg heavily
            const titleColor = cat.isAll ? 'text-bone dark:text-ink' : 'text-ink dark:text-bone group-hover:text-teal-800 dark:group-hover:text-teal-300';
            const subtitleColor = cat.isAll ? 'text-bone/80 dark:text-ink/80' : 'text-ink/70 dark:text-bone/70';

            return (
              <motion.button
                key={cat.id}
                onClick={() => {
                  onSelectCategory(cat.id);
                  onClose();
                }}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className={`group relative flex cursor-pointer flex-col justify-end overflow-hidden border border-line p-8 text-left transition-colors hover:border-teal-700 dark:hover:border-teal-400 min-h-[200px] md:min-h-[260px] ${cat.colSpan} ${cat.bg}`}
              >
                <div className="relative z-10">
                  <h3 className={`font-display text-4xl leading-none tracking-wide transition-colors ${titleColor}`}>
                    {cat.title}
                  </h3>
                  <p className={`mt-3 font-serif text-lg italic ${subtitleColor}`}>
                    {cat.subtitle}
                  </p>
                </div>
              </motion.button>
            );
          })}
        </motion.div>
      </div>
    </motion.div>
  );
}

