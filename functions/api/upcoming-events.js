const FEED = 'https://api.promo.ly/api/link-landers';
const CDN = 'https://cdn-prod-1.promo.ly/cdn-cgi/image/width=1200,height=1200,fit=scale-down,quality=80';

export async function readEvents(fetcher = (url, options) => fetch(url, options)) {
  const campaigns = [];
  const signal = AbortSignal.timeout(10000);
  let lastPage;
  for (let page = 1; page <= 10; page++) {
    // Fixed owner and origin: request parameters never control the upstream URL.
    const response = await fetcher(`${FEED}?ownerId=6079&page=${page}`, {
      signal,
      redirect: 'manual',
      cf: { cacheTtl: 300, cacheEverything: true },
    });
    if (!response.ok) throw new Error('Event feed unavailable');
    const body = await response.json();
    if (!Array.isArray(body.data) || body.current_page !== page ||
        !Number.isInteger(body.last_page) || body.last_page < page || body.last_page > 10 ||
        (lastPage !== undefined && body.last_page !== lastPage)) {
      throw new Error('Invalid event feed pagination');
    }
    lastPage = body.last_page;
    campaigns.push(...body.data);
    if (page === lastPage) break;
  }

  const events = new Map();
  for (const item of campaigns) {
    if (!item || !Number.isSafeInteger(item.id) || item.id < 1 ||
        typeof item.name !== 'string' || !item.name.trim() ||
        typeof item.releaseDate !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(item.releaseDate) ||
        !Number.isFinite(Date.parse(`${item.releaseDate}T00:00:00Z`)) ||
        new Date(`${item.releaseDate}T00:00:00Z`).toISOString().slice(0, 10) !== item.releaseDate ||
        item.assetsLocalPath !== `users/recondnb/promo.ly/campaigns/${item.id}` ||
        typeof item.packshotImage !== 'string' || !item.packshotImage.trim() ||
        /[/\\\u0000-\u001f]/.test(item.packshotImage)) continue;
    events.set(item.id, {
      id: item.id,
      title: item.name.trim(),
      date: item.releaseDate,
      image: `${CDN}/recondnb/promo.ly/campaigns/${item.id}/${encodeURIComponent(item.packshotImage)}`,
    });
  }
  // Keep dates in the response so an open OBS source can expire entries offline.
  return [...events.values()].sort((a, b) => a.date.localeCompare(b.date) || a.id - b.id);
}

export async function onRequest({ request }) {
  if (request.method !== 'GET') {
    return new Response(null, { status: 405, headers: { Allow: 'GET' } });
  }
  try {
    return Response.json({ events: await readEvents() }, {
      headers: { 'Cache-Control': 'public, max-age=60', 'X-Robots-Tag': 'noindex' },
    });
  } catch (error) {
    console.error('Recon event feed failed', error instanceof Error ? error.name : 'UnknownError');
    return Response.json({ error: 'Events temporarily unavailable' }, {
      status: 503,
      headers: { 'Cache-Control': 'no-store' },
    });
  }
}
