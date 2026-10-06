const fs = require('fs');

const path = 'src/views/LandingView.jsx';
let content = fs.readFileSync(path, 'utf8');

content = content.replace(
  "import { motion } from 'framer-motion';",
  "import { useState } from 'react';\nimport { motion, AnimatePresence } from 'framer-motion';\nimport { Maximize, X } from 'lucide-react';"
);

// Map Content Renderer function inside LandingView
// We will modify LandingView component
const MapContent = `
  const renderMap = (interactive = false) => (
    <>
      <img
        src={chennaiMap}
        alt="Road map of Chennai"
        draggable={false}
        className="size-full select-none invert hue-rotate-[200deg] dark:invert-0 dark:hue-rotate-[20deg] dark:drop-shadow-[0_0_6px_rgba(45,212,191,0.25)]"
      />
      <div className="pointer-events-none absolute inset-0" style={mapMask}>
        <motion.div
          className="absolute inset-x-0 h-1/5 bg-linear-to-b from-transparent via-teal-700/15 to-teal-700/45 dark:via-teal-300/20 dark:to-teal-200/60"
          animate={{ top: ['-20%', '100%'] }}
          transition={{ duration: 5, repeat: Infinity, ease: 'linear', repeatDelay: 1 }}
        />
      </div>
      {radarEvents.map((event, index) => (
        <RadarDot
          key={event.id}
          event={event}
          index={index}
          interactive={interactive}
          onExplore={onEnter}
        />
      ))}
    </>
  );
`;

content = content.replace(
  "export default function LandingView({ onEnter, theme, onToggleTheme }) {",
  "export default function LandingView({ onEnter, theme, onToggleTheme }) {\n  const [isFullscreen, setIsFullscreen] = useState(false);\n" + MapContent
);

// Replace the old map block with the scalable container and Expand button
const oldMapBlock = `
        {/* The map frame is taller than the panel (140%) and shifted up, cropping to the city core like a zoomed chart.
            Dots live inside the same frame so their percentage coordinates stay locked to the SVG. */}
        <div className="absolute left-1/2 top-1/2 aspect-[600/1155] h-[140%] -translate-x-1/2 -translate-y-[58%] lg:left-auto lg:right-[8%] lg:translate-x-0">
          <img
            src={chennaiMap}
            alt="Road map of Chennai"
            draggable={false}
            className="size-full select-none invert hue-rotate-[200deg] dark:invert-0 dark:hue-rotate-[20deg] dark:drop-shadow-[0_0_6px_rgba(45,212,191,0.25)]"
          />

          {/* Scan band is masked by the map itself, so it lights up only the roads it passes over */}
          <div className="pointer-events-none absolute inset-0" style={mapMask}>
            <motion.div
              className="absolute inset-x-0 h-1/5 bg-linear-to-b from-transparent via-teal-700/15 to-teal-700/45 dark:via-teal-300/20 dark:to-teal-200/60"
              animate={{ top: ['-20%', '100%'] }}
              transition={{ duration: 5, repeat: Infinity, ease: 'linear', repeatDelay: 1 }}
            />
          </div>

          {radarEvents.map((event, index) => (
            <RadarDot
              key={event.id}
              x={event.map_x}
              y={event.map_y}
              tone={event.isFree ? 'teal' : 'gold'}
              index={index}
              label={\`\${event.title} · \${event.area}\`}
            />
          ))}
        </div>
`;

const newMapBlock = `
        <motion.div 
          className="absolute inset-0"
          whileHover={!isFullscreen ? { scale: 1.05 } : {}}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        >
          <div className="absolute left-1/2 top-1/2 aspect-[600/1155] h-[140%] -translate-x-1/2 -translate-y-[58%] lg:left-auto lg:right-[8%] lg:translate-x-0">
            {renderMap(false)}
          </div>
        </motion.div>

        <button
          onClick={() => setIsFullscreen(true)}
          aria-label="Expand map"
          className="absolute right-6 top-6 z-30 grid size-10 place-items-center rounded-full border border-line bg-ivory/80 text-ink backdrop-blur-sm transition-colors hover:border-teal-700 hover:text-teal-700 dark:bg-ink/80 dark:text-bone dark:hover:border-teal-400 dark:hover:text-teal-400 lg:right-auto lg:left-6"
        >
          <Maximize className="size-4" strokeWidth={1.25} />
        </button>
`;

content = content.replace(oldMapBlock, newMapBlock);

// Append the Fullscreen Modal before the closing main tag
const fullscreenModal = `
      <AnimatePresence>
        {isFullscreen && (
          <motion.div
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.98 }}
            transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-ivory/95 backdrop-blur-md dark:bg-ink/95"
          >
            <button 
              onClick={() => setIsFullscreen(false)} 
              aria-label="Close map"
              className="absolute right-6 top-6 z-50 grid size-10 place-items-center rounded-full border border-line bg-ivory/80 text-ink backdrop-blur-sm transition-colors hover:border-teal-700 hover:text-teal-700 dark:bg-ink/80 dark:text-bone dark:hover:border-teal-400 dark:hover:text-teal-400"
            >
              <X className="size-4" strokeWidth={1.25} />
            </button>
            <div className="relative size-full overflow-auto">
              {/* Map scaled up */}
              <div className="relative mx-auto aspect-[600/1155] h-[150svh] md:h-[200svh]">
                {renderMap(true)}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.main>
`;

content = content.replace("    </motion.main>", fullscreenModal);

fs.writeFileSync(path, content);
console.log('Done');
