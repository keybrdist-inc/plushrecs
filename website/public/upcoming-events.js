const stage = document.querySelector('main');
const params = new URLSearchParams(window.location.search);
const timer = params.get('timer');
const seconds = /^\d+$/.test(timer || '') ? Number(timer) : NaN;
const interval = Number.isSafeInteger(seconds) && seconds >= 1 && seconds <= 2147483
  ? seconds * 1000 : 180000;
const id = params.get('id');
const selectedId = id === null ? null : (/^\d+$/.test(id) ? Number(id) : NaN);
const denverDate = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'America/Denver', year: 'numeric', month: '2-digit', day: '2-digit',
});
let events = [];
let current = null;
let refreshing = false;

function eligibleEvents(items = events) {
  if (selectedId !== null) {
    return Number.isSafeInteger(selectedId) && selectedId > 0
      ? items.filter(event => event.id === selectedId) : [];
  }
  const today = denverDate.format(new Date());
  return items.filter(event => event.date >= today);
}

function show(event) {
  if (event === current) return;
  const previous = current;
  current = event || null;
  if (current) {
    stage.append(current.element);
    // Commit initial opacity before beginning the crossfade.
    current.element.getBoundingClientRect();
    current.element.classList.add('active');
  }
  if (previous) {
    previous.element.classList.remove('active');
    setTimeout(() => {
      if (previous !== current) previous.element.remove();
    }, 850);
  }
}

function rotate() {
  const available = eligibleEvents();
  const index = available.indexOf(current);
  show(available[(index + 1) % available.length]);
}

async function loadImage(event) {
  const existing = events.find(old => old.id === event.id && old.image === event.image &&
    old.title === event.title && old.date === event.date);
  if (existing) return existing;
  const element = new Image();
  element.alt = event.title;
  element.decoding = 'async';
  element.draggable = false;
  element.src = event.image;
  let timeout;
  try {
    await Promise.race([
      element.decode(),
      new Promise((_, reject) => { timeout = setTimeout(() => reject(new Error('Image timeout')), 10000); }),
    ]);
    return { ...event, element };
  } catch {
    // A failed artwork replacement should not blank a previously loaded flyer.
    return events.find(old => old.id === event.id && old.date === event.date) || null;
  } finally {
    clearTimeout(timeout);
  }
}

async function refresh() {
  if (refreshing) return;
  refreshing = true;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch('/api/upcoming-events', {
      cache: 'no-cache', signal: controller.signal,
    });
    if (!response.ok) throw new Error('Event feed unavailable');
    const body = await response.json();
    if (!Array.isArray(body.events)) throw new Error('Invalid event feed');
    const next = eligibleEvents(body.events);
    events = (await Promise.all(next.map(loadImage))).filter(Boolean);
  } catch {
    // OBS stays on valid, loaded flyers during a temporary feed failure.
  } finally {
    clearTimeout(timeout);
    refreshing = false;
    const available = eligibleEvents();
    if (!available.includes(current)) show(available[0]);
  }
}

void refresh();
setInterval(rotate, interval);
setInterval(refresh, 5 * 60 * 1000);
