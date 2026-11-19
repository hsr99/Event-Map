import { useState, useId } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { UploadCloud, CheckCircle2, ArrowLeft, Sparkles, Image as ImageIcon } from 'lucide-react';
import EventCard from '../components/EventCard';
import { CHENNAI_VENUES } from '../data/venues';
import { events } from '../data/events';

const CATEGORIES = [
  { id: 'concerts', name: 'Concerts & Gigs' },
  { id: 'tech-events', name: 'Tech Events & Hackathons' },
  { id: 'social-gatherings', name: 'Social Gatherings & Walks' },
  { id: 'college-culturals', name: 'College Culturals' },
  { id: 'movies', name: 'Indie Movies & Screenings' },
];

export default function SubmitPosterView({ theme }) {
  const navigate = useNavigate();
  const fileInputId = useId();

  const [posterPreview, setPosterPreview] = useState(null);
  const [isExtracting, setIsExtracting] = useState(false);
  const [success, setSuccess] = useState(false);

  const [formData, setFormData] = useState({
    title: 'Chennai Indie Music Night',
    category: 'concerts',
    area: 'Besant Nagar',
    venue: "Elliot's Beach Promenade",
    date: '2026-11-20T19:00:00+05:30',
    price: 350,
    isFree: false,
    description: 'An open-air acoustic indie set right beside the sea breeze, featuring local songwriters and percussionists.',
    booking_link: '',
  });

  const handleImageChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const url = URL.createObjectURL(file);
    setPosterPreview(url);

    // Simulate smart VLM parsing for instant feedback
    setIsExtracting(true);
    setTimeout(() => {
      setIsExtracting(false);
    }, 900);
  };

  const handleVenueSelect = (venueName) => {
    const found = CHENNAI_VENUES.find((v) => v.name === venueName);
    if (found) {
      setFormData((prev) => ({
        ...prev,
        venue: found.name,
        area: found.area,
      }));
    } else {
      setFormData((prev) => ({ ...prev, venue: venueName }));
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();

    const selectedVenue = CHENNAI_VENUES.find((v) => v.name === formData.venue);
    const newEvent = {
      id: Date.now(),
      title: formData.title,
      category: formData.category,
      area: formData.area,
      venue: formData.venue,
      date: formData.date,
      price: formData.isFree ? 0 : Number(formData.price || 0),
      isFree: Boolean(formData.isFree),
      description: formData.description,
      image_url:
        posterPreview ||
        'https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=1200&q=80',
      lat: selectedVenue ? selectedVenue.lat : 13.04,
      lng: selectedVenue ? selectedVenue.lng : 80.24,
    };

    // Prepend to active event listings
    events.unshift(newEvent);
    setSuccess(true);

    setTimeout(() => {
      navigate('/events');
    }, 1200);
  };

  // Preview event object for EventCard
  const previewEvent = {
    id: 9999,
    title: formData.title || 'Untitled Event',
    category: formData.category,
    area: formData.area || 'Chennai',
    venue: formData.venue || 'Venue TBD',
    date: formData.date || new Date().toISOString(),
    price: formData.isFree ? 0 : Number(formData.price || 0),
    isFree: formData.isFree,
    description: formData.description,
    image_url:
      posterPreview ||
      'https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=1200&q=80',
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -16 }}
      className="min-h-svh px-6 pb-24 pt-10 lg:px-12 xl:px-16 2xl:px-24"
    >
      <div className="mx-auto max-w-6xl">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="group mb-8 inline-flex cursor-pointer items-center gap-3 text-sm transition-colors hover:text-teal-700 focus-visible:outline-1 focus-visible:outline-offset-4 focus-visible:outline-teal-600 dark:hover:text-teal-400"
        >
          <ArrowLeft className="size-4 transition-transform duration-300 group-hover:-translate-x-1" strokeWidth={1.25} />
          <span>Back</span>
        </button>

        <p className="flex items-center gap-3 text-[11px] uppercase tracking-[0.3em] text-muted">
          <span className="h-px w-8 bg-yellow-600 dark:bg-yellow-500" />
          Intake Pipeline · V1
        </p>
        <h1 className="mt-4 font-display text-6xl uppercase tracking-[0.02em] sm:text-8xl">
          Drop a Poster
        </h1>
        <p className="mt-4 max-w-2xl text-lg italic text-muted">
          Upload an event poster or flyer. Jarvis pins it on the Chennai radar map and publishes it across the listings.
        </p>

        <div className="mt-14 grid grid-cols-1 gap-12 lg:grid-cols-12">
          {/* Left Column: Upload & Form */}
          <form onSubmit={handleSubmit} className="space-y-8 lg:col-span-7">
            {/* Poster Upload Dropzone */}
            <div className="relative">
              <label
                htmlFor={fileInputId}
                className={`relative flex min-h-[220px] cursor-pointer flex-col items-center justify-center border-2 border-dashed p-6 text-center transition-all ${
                  posterPreview
                    ? 'border-teal-600/70 bg-teal-500/5'
                    : 'border-line hover:border-teal-700 dark:hover:border-teal-400'
                }`}
              >
                {posterPreview ? (
                  <div className="flex flex-col items-center gap-3">
                    <img
                      src={posterPreview}
                      alt="Uploaded poster"
                      className="max-h-48 rounded object-contain shadow-md"
                    />
                    <p className="text-xs uppercase tracking-wider text-teal-700 dark:text-teal-400 font-semibold">
                      Click or drag to replace poster
                    </p>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-3">
                    <div className="grid size-12 place-items-center rounded-full border border-line bg-ink/[0.03] dark:bg-bone/[0.03]">
                      <UploadCloud className="size-6 text-muted" strokeWidth={1.25} />
                    </div>
                    <div>
                      <p className="font-serif text-base text-ink dark:text-bone">
                        Drop your event flyer or poster here
                      </p>
                      <p className="text-xs italic text-muted mt-1">
                        PNG, JPG, or WEBP up to 10MB
                      </p>
                    </div>
                  </div>
                )}
                <input
                  id={fileInputId}
                  type="file"
                  accept="image/*"
                  onChange={handleImageChange}
                  className="sr-only"
                />
              </label>

              {isExtracting && (
                <div className="absolute inset-0 z-10 flex items-center justify-center bg-ivory/80 backdrop-blur-sm dark:bg-ink/80">
                  <div className="flex items-center gap-3 text-sm font-serif italic text-teal-700 dark:text-teal-400">
                    <Sparkles className="size-4 animate-spin" />
                    <span>Extracting event details...</span>
                  </div>
                </div>
              )}
            </div>

            {/* Event Name */}
            <div>
              <label className="block text-xs uppercase tracking-widest text-muted mb-2 font-serif">
                Event Title *
              </label>
              <input
                type="text"
                required
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                className="w-full border-b border-line bg-transparent py-2.5 outline-none font-serif text-lg focus:border-teal-700 dark:focus:border-teal-400 transition-colors"
                placeholder="e.g. Margazhi Rooftop Baithak"
              />
            </div>

            {/* Category */}
            <div>
              <label className="block text-xs uppercase tracking-widest text-muted mb-2 font-serif">
                Category *
              </label>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                {CATEGORIES.map((cat) => (
                  <button
                    key={cat.id}
                    type="button"
                    onClick={() => setFormData({ ...formData, category: cat.id })}
                    className={`cursor-pointer border p-3 text-left text-xs font-serif transition-colors ${
                      formData.category === cat.id
                        ? 'border-teal-700 bg-teal-700/10 text-teal-800 dark:border-teal-400 dark:bg-teal-400/10 dark:text-teal-300'
                        : 'border-line text-muted hover:border-ink/40 dark:hover:border-bone/40'
                    }`}
                  >
                    {cat.name}
                  </button>
                ))}
              </div>
            </div>

            {/* Venue & Neighbourhood */}
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
              <div>
                <label className="block text-xs uppercase tracking-widest text-muted mb-2 font-serif">
                  Venue *
                </label>
                <input
                  type="text"
                  required
                  list="chennai-venues-list"
                  value={formData.venue}
                  onChange={(e) => handleVenueSelect(e.target.value)}
                  className="w-full border-b border-line bg-transparent py-2.5 outline-none font-serif text-base focus:border-teal-700 dark:focus:border-teal-400 transition-colors"
                  placeholder="e.g. Backyard, Adyar"
                />
                <datalist id="chennai-venues-list">
                  {CHENNAI_VENUES.map((v) => (
                    <option key={v.name} value={v.name}>
                      {v.area}
                    </option>
                  ))}
                </datalist>
              </div>

              <div>
                <label className="block text-xs uppercase tracking-widest text-muted mb-2 font-serif">
                  Neighbourhood / Area *
                </label>
                <input
                  type="text"
                  required
                  value={formData.area}
                  onChange={(e) => setFormData({ ...formData, area: e.target.value })}
                  className="w-full border-b border-line bg-transparent py-2.5 outline-none font-serif text-base focus:border-teal-700 dark:focus:border-teal-400 transition-colors"
                  placeholder="e.g. Adyar, Besant Nagar"
                />
              </div>
            </div>

            {/* Date and Time */}
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
              <div>
                <label className="block text-xs uppercase tracking-widest text-muted mb-2 font-serif">
                  Date & Time *
                </label>
                <input
                  type="datetime-local"
                  required
                  value={formData.date.slice(0, 16)}
                  onChange={(e) => setFormData({ ...formData, date: `${e.target.value}:00+05:30` })}
                  className="w-full border-b border-line bg-transparent py-2.5 outline-none font-serif text-base focus:border-teal-700 dark:focus:border-teal-400 transition-colors"
                />
              </div>

              <div>
                <label className="block text-xs uppercase tracking-widest text-muted mb-2 font-serif">
                  Admission
                </label>
                <div className="flex items-center gap-6 pt-2">
                  <label className="flex items-center gap-2 cursor-pointer text-sm">
                    <input
                      type="checkbox"
                      checked={formData.isFree}
                      onChange={(e) => setFormData({ ...formData, isFree: e.target.checked })}
                      className="size-4 accent-teal-600"
                    />
                    <span>Free Entry</span>
                  </label>

                  {!formData.isFree && (
                    <div className="flex items-center gap-2">
                      <span className="text-muted">₹</span>
                      <input
                        type="number"
                        min="0"
                        value={formData.price}
                        onChange={(e) => setFormData({ ...formData, price: e.target.value })}
                        placeholder="Price"
                        className="w-24 border-b border-line bg-transparent py-1 text-sm outline-none focus:border-teal-700 dark:focus:border-teal-400"
                      />
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Description */}
            <div>
              <label className="block text-xs uppercase tracking-widest text-muted mb-2 font-serif">
                Description
              </label>
              <textarea
                rows={3}
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="w-full border border-line bg-transparent p-3 outline-none font-serif text-sm focus:border-teal-700 dark:focus:border-teal-400 transition-colors"
                placeholder="Briefly describe the experience, artists, and vibe..."
              />
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={success}
              className="cursor-pointer group flex items-center justify-center gap-3 bg-ink px-8 py-4 font-display text-xl tracking-[0.14em] text-ivory transition-colors hover:bg-teal-700 focus-visible:outline-1 focus-visible:outline-teal-600 dark:bg-bone dark:text-ink dark:hover:bg-teal-400 disabled:opacity-50 w-full sm:w-auto"
            >
              {success ? (
                <>
                  <CheckCircle2 className="size-5 text-teal-400" />
                  <span>Added to Chennai Radar!</span>
                </>
              ) : (
                <span>Publish to Chennai Map</span>
              )}
            </button>
          </form>

          {/* Right Column: Live Card Preview */}
          <div className="lg:col-span-5">
            <div className="sticky top-28 space-y-4">
              <div className="flex items-center gap-2 text-xs uppercase tracking-widest text-muted">
                <ImageIcon className="size-3.5" />
                <span>Live Card Preview</span>
              </div>
              <div className="max-w-sm">
                <EventCard event={previewEvent} onSelect={() => {}} />
              </div>
              <p className="text-xs italic text-muted max-w-sm">
                This is how your event will appear in the directory and radar map popups once submitted.
              </p>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
