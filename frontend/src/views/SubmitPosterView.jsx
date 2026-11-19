import { useState, useId } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { UploadCloud, CheckCircle2, ArrowLeft, Sparkles, Image as ImageIcon, AlertCircle } from 'lucide-react';
import EventCard from '../components/EventCard';
import { CHENNAI_VENUES } from '../data/venues';
import { API_URL, errorMessage } from '../lib/api';

const CATEGORIES = [
  { id: 'concerts', name: 'Concerts & Gigs' },
  { id: 'tech-events', name: 'Tech Events & Hackathons' },
  { id: 'social-gatherings', name: 'Social Gatherings & Walks' },
  { id: 'college-culturals', name: 'College Culturals' },
  { id: 'movies', name: 'Indie Movies & Screenings' },
];

export default function SubmitPosterView() {
  const navigate = useNavigate();
  const fileInputId = useId();

  const [posterPreview, setPosterPreview] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [isExtracting, setIsExtracting] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [success, setSuccess] = useState(null); // server message once submitted
  const [submitError, setSubmitError] = useState('');
  const [extractNote, setExtractNote] = useState('');

  const [formData, setFormData] = useState({
    title: '',
    category: '', // blank = let the poster decide
    area: '',
    venue: '',
    date: '',
    price: '', // blank = unknown, read from the poster
    isFree: false,
    description: '',
    booking_link: '',
    contact_phone: '',
    instagram: '',
    contact: '',
  });

  const handleImageChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setSelectedFile(file);
    const url = URL.createObjectURL(file);
    setPosterPreview(url);

    // Ask the backend to read the poster and pre-fill the form
    setIsExtracting(true);
    setExtractNote('');
    try {
      const body = new FormData();
      body.append('poster', file);
      const res = await fetch(`${API_URL}/api/extract`, { method: 'POST', body });
      if (!res.ok) {
        setExtractNote(`${await errorMessage(res)} You can still fill in the details by hand.`);
        return;
      }
      const data = await res.json();
      setFormData((prev) => ({
        ...prev,
        title: data.title || prev.title,
        category: data.category || prev.category,
        venue: data.venue || prev.venue,
        area: data.area || prev.area,
        date: data.date || prev.date,
        price: data.price !== undefined ? data.price : prev.price,
        isFree: data.is_free !== undefined ? data.is_free : prev.isFree,
        description: data.description || prev.description,
        booking_link: data.booking_link || prev.booking_link,
        contact_phone: data.contact_phone || prev.contact_phone,
        instagram: data.instagram || prev.instagram,
      }));
      const unread = [!data.date && 'date', !data.venue && 'venue'].filter(Boolean);
      setExtractNote(
        unread.length
          ? `Couldn't spot the ${unread.join(' or ')} on the poster. Add it if you know it, or submit anyway and we'll sort it out in review.`
          : 'Filled in from the poster. Fix anything we got wrong, then submit.',
      );
    } catch {
      setExtractNote("Couldn't reach the server to read the poster. Fill in the details by hand.");
    } finally {
      setIsExtracting(false);
    }
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

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitError('');
    setIsSubmitting(true);
    try {
      const body = new FormData();
      if (selectedFile) body.append('poster', selectedFile);
      body.append('title', formData.title);
      body.append('category', formData.category);
      body.append('venue', formData.venue);
      body.append('area', formData.area);
      body.append('date', formData.date);
      body.append('price', formData.isFree ? '0' : String(formData.price ?? '').trim());
      body.append('is_free', String(formData.isFree));
      body.append('description', formData.description || '');
      body.append('booking_link', formData.booking_link || '');
      body.append('contact_phone', formData.contact_phone || '');
      body.append('instagram', formData.instagram || '');
      body.append('contact', formData.contact || '');

      const res = await fetch(`${API_URL}/api/submit`, { method: 'POST', body });
      if (!res.ok) {
        setSubmitError(await errorMessage(res));
        return;
      }
      const saved = await res.json();
      setSuccess(saved.message || "Thanks! Your event will appear on the map once it's reviewed.");
    } catch {
      setSubmitError("Couldn't reach the server. Check your connection and try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const hasPoster = Boolean(selectedFile);
  const canSubmit = hasPoster || Boolean(formData.title.trim() && formData.date && formData.venue.trim());
  const needsReading = hasPoster && !(formData.title && formData.date && formData.venue);

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
          Just drop the poster, that's all we need. Jarvis reads the date, venue and the rest off it, and once a quick review is done it's pinned on the Chennai map.
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

              {extractNote && !isExtracting && (
                <p className="mt-3 flex items-start gap-2 text-xs italic text-muted">
                  <AlertCircle className="mt-0.5 size-3.5 shrink-0" />
                  <span>{extractNote}</span>
                </p>
              )}

              {isExtracting && (
                <div className="absolute inset-0 z-10 flex items-center justify-center bg-ivory/80 backdrop-blur-sm dark:bg-ink/80">
                  <div className="flex items-center gap-3 text-sm font-serif italic text-teal-700 dark:text-teal-400">
                    <Sparkles className="size-4 animate-spin" />
                    <span>Extracting event details...</span>
                  </div>
                </div>
              )}
            </div>

            <p className="border-l-2 border-teal-600/60 pl-3 text-sm italic text-muted">
              {hasPoster
                ? 'Everything below is optional. It fills in from your poster; fix anything that looks wrong.'
                : 'No poster? Fill in at least the title, date and venue.'}
            </p>

            {/* Event Name */}
            <div>
              <label className="block text-xs uppercase tracking-widest text-muted mb-2 font-serif">
                Event Title
              </label>
              <input
                type="text"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                className="w-full border-b border-line bg-transparent py-2.5 outline-none font-serif text-lg focus:border-teal-700 dark:focus:border-teal-400 transition-colors"
                placeholder="e.g. Margazhi Rooftop Baithak"
              />
            </div>

            {/* Category */}
            <div>
              <label className="block text-xs uppercase tracking-widest text-muted mb-2 font-serif">
                Category
              </label>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                {CATEGORIES.map((cat) => (
                  <button
                    key={cat.id}
                    type="button"
                    aria-pressed={formData.category === cat.id}
                    onClick={() =>
                      setFormData({ ...formData, category: formData.category === cat.id ? '' : cat.id })
                    }
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
                  Venue
                </label>
                <input
                  type="text"
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
                  Neighbourhood / Area
                </label>
                <input
                  type="text"
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
                  Date & Time
                </label>
                <input
                  type="datetime-local"
                  value={formData.date.slice(0, 16)}
                  onChange={(e) =>
                    setFormData({ ...formData, date: e.target.value ? `${e.target.value}:00+05:30` : '' })
                  }
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

            {/* Organiser's public contact, for bookings */}
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
              <div>
                <label className="block text-xs uppercase tracking-widest text-muted mb-2 font-serif">
                  Organiser's Instagram
                </label>
                <input
                  type="text"
                  value={formData.instagram}
                  onChange={(e) => setFormData({ ...formData, instagram: e.target.value })}
                  className="w-full border-b border-line bg-transparent py-2.5 outline-none font-serif text-base focus:border-teal-700 dark:focus:border-teal-400 transition-colors"
                  placeholder="@handle"
                />
              </div>
              <div>
                <label className="block text-xs uppercase tracking-widest text-muted mb-2 font-serif">
                  Organiser's Phone (for bookings)
                </label>
                <input
                  type="tel"
                  value={formData.contact_phone}
                  onChange={(e) => setFormData({ ...formData, contact_phone: e.target.value })}
                  className="w-full border-b border-line bg-transparent py-2.5 outline-none font-serif text-base focus:border-teal-700 dark:focus:border-teal-400 transition-colors"
                  placeholder="98765 43210"
                />
              </div>
            </div>

            {/* Booking link & contact */}
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
              <div>
                <label className="block text-xs uppercase tracking-widest text-muted mb-2 font-serif">
                  Booking / RSVP Link
                </label>
                <input
                  type="url"
                  value={formData.booking_link}
                  onChange={(e) => setFormData({ ...formData, booking_link: e.target.value })}
                  className="w-full border-b border-line bg-transparent py-2.5 outline-none font-serif text-base focus:border-teal-700 dark:focus:border-teal-400 transition-colors"
                  placeholder="https://"
                />
              </div>
              <div>
                <label className="block text-xs uppercase tracking-widest text-muted mb-2 font-serif">
                  Your Contact (private)
                </label>
                <input
                  type="text"
                  value={formData.contact}
                  onChange={(e) => setFormData({ ...formData, contact: e.target.value })}
                  className="w-full border-b border-line bg-transparent py-2.5 outline-none font-serif text-base focus:border-teal-700 dark:focus:border-teal-400 transition-colors"
                  placeholder="Email or phone, in case we have questions"
                />
              </div>
            </div>

            {submitError && (
              <p role="alert" className="flex items-start gap-2 border border-rose-500/40 bg-rose-500/5 p-3 text-sm text-rose-700 dark:text-rose-300">
                <AlertCircle className="mt-0.5 size-4 shrink-0" />
                <span>{submitError}</span>
              </p>
            )}

            {success && (
              <p role="status" className="flex items-start gap-2 border border-teal-600/40 bg-teal-500/5 p-3 text-sm text-teal-800 dark:text-teal-300">
                <CheckCircle2 className="mt-0.5 size-4 shrink-0" />
                <span>{success}</span>
              </p>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              disabled={Boolean(success) || isSubmitting || !canSubmit}
              className="cursor-pointer group flex items-center justify-center gap-3 bg-ink px-8 py-4 font-display text-xl tracking-[0.14em] text-ivory transition-colors hover:bg-teal-700 focus-visible:outline-1 focus-visible:outline-teal-600 dark:bg-bone dark:text-ink dark:hover:bg-teal-400 disabled:opacity-50 w-full sm:w-auto"
            >
              {success ? (
                <>
                  <CheckCircle2 className="size-5 text-teal-400" />
                  <span>Submitted for review</span>
                </>
              ) : (
                <span>
                  {isSubmitting ? (needsReading ? 'Reading poster & submitting…' : 'Submitting…') : 'Submit for review'}
                </span>
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
                This is how your event will appear in the listings and on the map once it's approved.
              </p>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
