import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';

const CATEGORIES = [
  { id: 'college-culturals', title: 'College Culturals', subtitle: 'The biggest student-run fests in the city', colSpan: 'col-span-1 md:col-span-2', bg: 'bg-gradient-to-br from-teal-900/40 to-ink dark:from-teal-900/20 dark:to-ink' },
  { id: 'tech-events', title: 'Tech Events', subtitle: 'Hackathons, summits & builder meetups', colSpan: 'col-span-1', bg: 'bg-gradient-to-bl from-neutral-200 to-ivory dark:from-neutral-800 dark:to-ink' },
  { id: 'movies', title: 'Movies', subtitle: 'Indie screenings & retrospectives', colSpan: 'col-span-1', bg: 'bg-neutral-100 dark:bg-neutral-900' },
  { id: 'concerts', title: 'Concerts', subtitle: 'Live music, indie gigs & electronic nights', colSpan: 'col-span-1 md:col-span-2', bg: 'bg-gradient-to-tr from-yellow-700/20 to-ivory dark:from-yellow-900/20 dark:to-ink' },
  { id: 'social-gatherings', title: 'Social Gatherings', subtitle: 'Food walks, supper clubs & heritage tours', colSpan: 'col-span-1 md:col-span-3', bg: 'bg-gradient-to-r from-stone-200 to-ivory dark:from-stone-900 dark:to-ink' },
];

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.1 } },
  exit: { opacity: 0, transition: { duration: 0.3 } },
};

const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.22, 1, 0.36, 1] } },
};

export default function CategoryHub({ theme, onToggleTheme }) {
  const navigate = useNavigate();

  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="show"
      exit="exit"
      className="min-h-svh px-6 lg:px-12 xl:px-16 2xl:px-24"
    >
      <main className="mx-auto max-w-6xl py-20">
        <motion.p variants={item} className="flex items-center gap-4 text-[11px] uppercase tracking-[0.3em] text-muted">
          <span className="h-px w-10 bg-yellow-600 dark:bg-yellow-500" />
          Intel Categories
        </motion.p>
        <motion.h1 variants={item} className="mt-6 font-display text-6xl leading-[0.85] tracking-[0.02em] sm:text-8xl">
          Explore Chennai
        </motion.h1>
        <motion.p variants={item} className="mt-4 max-w-xl text-lg italic text-muted">
          Discover what the city has to offer through our curated collections.
        </motion.p>

        <motion.div variants={item} className="mt-16 grid grid-cols-1 gap-6 md:grid-cols-3">
          {CATEGORIES.map((cat) => (
            <motion.button
              key={cat.id}
              onClick={() => navigate(`/events/${cat.id}`)}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className={`cursor-pointer group relative flex flex-col justify-end overflow-hidden border border-line p-8 text-left transition-colors hover:border-teal-700 dark:hover:border-teal-400 min-h-[240px] md:min-h-[320px] ${cat.colSpan} ${cat.bg}`}
            >
              <div className="relative z-10">
                <h2 className="font-display text-4xl leading-none tracking-wide text-ink transition-colors group-hover:text-teal-800 dark:text-bone dark:group-hover:text-teal-300">
                  {cat.title}
                </h2>
                <p className="mt-3 font-serif text-lg italic text-ink/70 dark:text-bone/70">
                  {cat.subtitle}
                </p>
              </div>
            </motion.button>
          ))}
        </motion.div>
      </main>
    </motion.div>
  );
}

