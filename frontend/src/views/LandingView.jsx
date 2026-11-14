import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import chennaiMap from '../assets/chennai-map.svg';
import { events } from '../data/events';

const stats = [
  [events.length, 'Listings'],
  [new Set(events.map((event) => event.area)).size, 'Neighbourhoods'],
  [events.filter((event) => event.isFree).length, 'Free to attend'],
];

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.12, delayChildren: 0.1 } },
  exit: { opacity: 0, y: -24, filter: 'blur(6px)', transition: { duration: 0.4, ease: 'easeIn' } },
};

const item = {
  hidden: { opacity: 0, y: 28 },
  show: { opacity: 1, y: 0, transition: { duration: 0.7, ease: [0.22, 1, 0.36, 1] } },
};

const reveal = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { duration: 1.2, ease: 'easeOut' } },
};

const mapMask = {
  maskImage: `url(${chennaiMap})`,
  WebkitMaskImage: `url(${chennaiMap})`,
  maskSize: '100% 100%',
  WebkitMaskSize: '100% 100%',
};

export default function LandingView({ theme, onToggleTheme }) {
  const navigate = useNavigate();
  return (
    <>
      <motion.main
        variants={container}
        initial="hidden"
        animate="show"
        exit="exit"
        className="relative grid min-h-svh grid-cols-1 lg:grid-cols-[3fr_2fr]"
      >

        <motion.section
          variants={reveal}
          aria-label="Live map of Chennai events"
          className="relative h-[68svh] overflow-hidden border-b border-line bg-ink/[0.025] lg:h-auto lg:min-h-svh lg:border-b-0 lg:border-r dark:bg-bone/[0.015]"
        >
          {/* Static SVG Map Container (no hover animations) */}
          <div
            className="absolute left-1/2 top-1/2 aspect-[600/1155] h-[140%] -translate-x-1/2 -translate-y-[58%] lg:left-auto lg:right-[8%] lg:translate-x-0"
          >
            <img
              src={chennaiMap}
              alt="Road map of Chennai"
              draggable={false}
              className="size-full select-none invert hue-rotate-[200deg] dark:invert-0 dark:hue-rotate-[20deg] dark:drop-shadow-[0_0_6px_rgba(45,212,191,0.25)]"
            />
            {/* Scan band */}
            <div className="pointer-events-none absolute inset-0" style={mapMask}>
              <motion.div
                className="absolute inset-x-0 h-1/5 bg-linear-to-b from-transparent via-teal-700/15 to-teal-700/45 dark:via-teal-300/20 dark:to-teal-200/60"
                animate={{ top: ['-20%', '100%'] }}
                transition={{ duration: 5, repeat: Infinity, ease: 'linear', repeatDelay: 1 }}
              />
            </div>
          </div>

          {/* <p className="absolute left-6 top-7 z-20 text-xs italic text-muted"> (???) Chennai</p> */}
          {/* <div className="absolute bottom-6 left-6 z-20 flex gap-6 text-xs text-muted">
            <span className="flex items-center gap-2">
              <span className="size-2 rounded-full bg-teal-600 dark:bg-teal-400" /> Free entry
            </span>
            <span className="flex items-center gap-2">
              <span className="size-2 rounded-full bg-yellow-500" /> Ticketed
            </span>
          </div> */}
        </motion.section>

        <section className="flex flex-col justify-center px-8 py-16 sm:px-12 lg:px-14 xl:px-20">
          <motion.p variants={item} className="flex items-center gap-4 text-[11px] uppercase tracking-[0.3em] text-muted">
            <span className="h-px w-10 bg-yellow-600 dark:bg-yellow-500" />
            Chennai · Est. 2026
          </motion.p>

          <motion.h1
            variants={item}
            className="mt-8 font-display text-[clamp(6rem,11vw,11rem)] leading-[0.82] tracking-[0.02em]"
          >
            JARVIS
          </motion.h1>

          <motion.p variants={item} className="mt-4 text-2xl font-light italic sm:text-3xl">
            The Chennai Event Map
          </motion.p>

          <motion.p variants={item} className="mt-6 max-w-sm leading-relaxed text-muted">
            An unhurried guide to the city after dark — concerts, supper clubs, gallery openings and match nights,
            gathered from Royapuram to Sholinganallur.
          </motion.p>

          <motion.button
            variants={item}
            type="button"
            onClick={() => navigate('/events')}
            aria-label="Explore the listings"
            className="group mt-14 inline-flex cursor-pointer items-center gap-4 self-start bg-ink px-7 pb-3.5 pt-4 font-display text-xl tracking-[0.14em] text-ivory transition-colors duration-300 hover:bg-teal-700 focus-visible:outline-1 focus-visible:outline-offset-4 focus-visible:outline-teal-600 dark:bg-bone dark:text-ink dark:hover:bg-teal-400"
          >
            Explore the listings
            <motion.span
              className="flex items-center"
              animate={{ x: [0, 6, 0] }}
              transition={{ duration: 1.6, repeat: Infinity, repeatDelay: 2.6, ease: 'easeInOut', delay: 2 }}
            >
              <svg viewBox="0 0 31 24" aria-hidden className="-mt-1 h-3.5 w-auto">
                <path d="M1 4L6 4L14 12L6 20L1 20L9 12Z M9 4L14 4L22 12L14 20L9 20L17 12Z M17 4L22 4L30 12L22 20L17 20L25 12Z" fill="currentColor" />
              </svg>
            </motion.span>
          </motion.button>

          <motion.dl variants={item} className="mt-20 grid max-w-sm grid-cols-3 gap-6 border-t border-line pt-6">
            {stats.map(([value, label]) => (
              <div key={label} className="flex flex-col-reverse">
                <dt className="mt-2 text-xs italic text-muted">{label}</dt>
                <dd className="font-display text-4xl leading-none">{String(value).padStart(2, '0')}</dd>
              </div>
            ))}
          </motion.dl>
        </section>
      </motion.main>
    </>
  );
}
