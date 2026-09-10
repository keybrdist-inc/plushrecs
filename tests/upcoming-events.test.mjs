import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test, mock } from 'node:test';
import vm from 'node:vm';
import { readEvents, onRequest } from '../functions/api/upcoming-events.js';

const campaign = (id, date = '2026-09-12', overrides = {}) => ({
  id, name: `Event ${id}`, releaseDate: date,
  assetsLocalPath: `users/recondnb/promo.ly/campaigns/${id}`,
  packshotImage: 'Flyer square.png', ...overrides,
});
const page = (data, current_page = 1, last_page = 1) =>
  Response.json({ data, current_page, last_page });

test('reads every page, sorts events, and returns only public flyer fields', async () => {
  const requests = [];
  const events = await readEvents(async (url, options) => {
    requests.push({ url, options });
    return requests.length === 1
      ? page([campaign(2, '2026-10-10', { privateEmail: 'must-not-be-returned' })], 1, 2)
      : page([campaign(1), campaign(1)], 2, 2);
  });
  assert.deepEqual(events.map(e => e.id), [1, 2]);
  assert.deepEqual(Object.keys(events[0]).sort(), ['date', 'id', 'image', 'title']);
  assert.equal(events[0].image, 'https://cdn-prod-1.promo.ly/cdn-cgi/image/width=1200,height=1200,fit=scale-down,quality=80/recondnb/promo.ly/campaigns/1/Flyer%20square.png');
  assert.equal(requests[1].url, 'https://api.promo.ly/api/link-landers?ownerId=6079&page=2');
  assert.equal(requests[0].options.redirect, 'manual');
  assert.equal(requests[0].options.signal, requests[1].options.signal);
});

test('rejects incomplete, excessive, or inconsistent pagination', async () => {
  await assert.rejects(readEvents(async () => page([], 1, 11)));
  await assert.rejects(readEvents(async () => Response.json({ data: [] })));
  await assert.rejects(readEvents(async () => new Response(null, {
    status: 302, headers: { Location: 'https://example.com' },
  })));
  let calls = 0;
  await assert.rejects(readEvents(async () => ++calls === 1
    ? page([campaign(1)], 1, 2) : page([], 2, 3)));
  calls = 0;
  await assert.rejects(readEvents(async () => ++calls === 1
    ? page([campaign(1)], 1, 2) : new Response('unavailable', { status: 503 })));
});

test('excludes malformed dates, invalid records, and foreign image paths', async () => {
  const events = await readEvents(async () => page([
    null, campaign(1, '2026-02-30'), campaign(2, 'tomorrow'),
    campaign(3, undefined, { assetsLocalPath: 'users/another-account' }),
    campaign(4, undefined, { packshotImage: '../outside.png' }),
    campaign(5, undefined, { packshotImage: '' }),
    campaign(6, undefined, { name: null }), campaign(7),
  ]));
  assert.deepEqual(events.map(e => e.id), [7]);
});

test('API fixes the upstream owner, denies writes, and does not leak failure details', async () => {
  const requests = [];
  const fetchMock = mock.method(globalThis, 'fetch', async url => {
    requests.push(url);
    return page([]);
  });
  try {
    const request = new Request('https://about.plushrecs.com/api/upcoming-events?ownerId=999&url=https://example.com');
    const response = await onRequest({ request });
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { events: [] });
    assert.equal(requests[0], 'https://api.promo.ly/api/link-landers?ownerId=6079&page=1');
    const denied = await onRequest({ request: new Request(request, { method: 'POST' }) });
    assert.equal(denied.status, 405);
    assert.equal(requests.length, 1);
    fetchMock.mock.mockImplementation(async () => { throw new Error('internal diagnostic'); });
    const failed = await onRequest({ request });
    assert.equal(failed.status, 503);
    assert.equal(failed.headers.get('cache-control'), 'no-store');
    assert.deepEqual(await failed.json(), { error: 'Events temporarily unavailable' });
  } finally {
    fetchMock.mock.restore();
  }
});

const clientSource = await readFile(new URL('../website/public/upcoming-events.js', import.meta.url), 'utf8');
const event = (id, date = '2026-09-12') => ({ id, date, title: `Event ${id}`, image: `https://example.com/${id}.jpg` });

async function browser(initial, search = '') {
  let now = '2026-09-13T05:59:59Z'; // Still September 12 in Denver.
  let feed = initial;
  const broken = new Set();
  const intervals = new Map();
  const timeouts = new Map();
  const elements = new Set();
  const requests = [];
  let timerId = 0;
  let elapsed = 0;
  class Image {
    classList = { add: () => { this.active = true; }, remove: () => { this.active = false; } };
    decode() { return broken.has(this.src) ? Promise.reject(new Error('broken image')) : Promise.resolve(); }
    getBoundingClientRect() { return {}; }
    remove() { elements.delete(this); }
  }
  const stage = { append: element => elements.add(element) };
  const context = vm.createContext({
    Image, Intl, AbortController, AbortSignal: {}, // Chromium 95 has no AbortSignal.timeout().
    URLSearchParams, window: { location: { search } },
    Date: class extends Date { constructor() { super(now); } },
    document: { querySelector: () => stage },
    fetch: async (url, options) => {
      requests.push({ url, signal: options.signal });
      if (typeof feed === 'function') return feed(options.signal);
      if (feed instanceof Error) throw feed;
      return { ok: true, json: async () => ({ events: feed }) };
    },
    setInterval: (fn, delay) => { intervals.set(fn.name, { fn, delay, next: elapsed + delay }); },
    setTimeout: (fn, delay) => { const id = ++timerId; timeouts.set(id, { fn, delay }); return id; },
    clearTimeout: id => timeouts.delete(id),
  });
  const settle = async () => { for (let i = 0; i < 20; i++) await Promise.resolve(); };
  vm.runInContext(clientSource, context);
  await settle();
  return {
    broken,
    requests,
    active: () => [...elements].filter(e => e.active).map(e => e.alt),
    advance: value => { now = value; },
    rotate: () => { intervals.get('rotate').fn(); },
    refresh: async value => { feed = value; await intervals.get('refresh').fn(); await settle(); },
    tick: async duration => {
      const end = elapsed + duration;
      while (true) {
        const next = [...intervals.values()].sort((a, b) => a.next - b.next)[0];
        if (next.next > end) break;
        elapsed = next.next;
        next.next += next.delay;
        next.fn();
        await settle();
      }
      elapsed = end;
    },
    finishFade: () => {
      for (const [id, timer] of timeouts) if (timer.delay === 850) { timer.fn(); timeouts.delete(id); }
    },
    elementCount: () => elements.size,
    pendingRequestTimers: () => [...timeouts.values()].filter(timer => timer.delay === 15000).length,
    expireRequest: async () => {
      for (const timer of timeouts.values()) if (timer.delay === 15000) timer.fn();
      await settle();
    },
  };
}

test('default rotation holds each flyer for 180 seconds', async () => {
  const b = await browser([event(1), event(2)]);
  await b.tick(179999);
  assert.deepEqual(b.active(), ['Event 1']);
  await b.tick(1);
  assert.deepEqual(b.active(), ['Event 2']);
  await b.tick(180000);
  assert.deepEqual(b.active(), ['Event 1']);
});

test('timer query overrides rotation without changing the five-minute feed refresh', async () => {
  const b = await browser([event(1), event(2)], '?timer=60');
  await b.tick(59999);
  assert.deepEqual(b.active(), ['Event 1']);
  await b.tick(1);
  assert.deepEqual(b.active(), ['Event 2']);
  assert.equal(b.requests.length, 1);
  await b.tick(240000);
  assert.equal(b.requests.length, 2);
  assert.deepEqual(b.active(), ['Event 2']);
  const sameInterval = await browser([event(1), event(2)], '?timer=300');
  await sameInterval.tick(300000);
  assert.deepEqual(sameInterval.active(), ['Event 2']);
  assert.equal(sameInterval.requests.length, 2);
});

test('invalid timer values safely fall back to 180 seconds', async () => {
  for (const timer of ['', '0', '-1', '0.5', '180oops', 'NaN', 'Infinity', '2147484', '999999999999999999999']) {
    const b = await browser([event(1), event(2)], `?timer=${timer}`);
    await b.tick(179999);
    assert.deepEqual(b.active(), ['Event 1'], `timer=${timer}`);
    await b.tick(1);
    assert.deepEqual(b.active(), ['Event 2'], `timer=${timer}`);
  }
});

test('id pins the actual campaign rather than its position in the feed', async () => {
  const b = await browser([event(24019), event(24044)], '?id=24044&timer=1');
  assert.deepEqual(b.active(), ['Event 24044']);
  await b.tick(300000);
  assert.deepEqual(b.active(), ['Event 24044']);
  assert.equal(b.requests.length, 2);
  await b.refresh([{ ...event(24044), title: 'Updated flyer' }, event(24019)]);
  assert.deepEqual(b.active(), ['Updated flyer']);
});

test('pinned flyers remain eligible after their date and through temporary feed failures', async () => {
  const b = await browser([event(1, '2026-09-11'), event(2)], '?id=1');
  assert.deepEqual(b.active(), ['Event 1']);
  b.advance('2026-09-14T06:00:00Z');
  b.rotate();
  await b.refresh(new Error('offline'));
  assert.deepEqual(b.active(), ['Event 1']);
  await b.refresh([event(2)]);
  assert.deepEqual(b.active(), []);
});

test('unknown or invalid ids stay black instead of showing an unrelated flyer', async () => {
  for (const id of ['1', '', '0', '-1', '24019oops', '1.5', '999999999999999999999']) {
    const b = await browser([event(24019)], `?id=${id}`);
    assert.deepEqual(b.active(), [], `id=${id}`);
    b.rotate();
    assert.deepEqual(b.active(), [], `id=${id}`);
  }
  const b = await browser([event(24019)], '?id=24044');
  await b.refresh([event(24019), event(24044)]);
  assert.deepEqual(b.active(), ['Event 24044']);
});

test('browser loads flyers without AbortSignal.timeout and clears the request timer', async () => {
  const b = await browser([event(1)]);
  assert.deepEqual(b.active(), ['Event 1']);
  assert.equal(b.requests.length, 1);
  assert.equal(b.requests[0].signal.aborted, false);
  assert.equal(b.pendingRequestTimers(), 0);
  await b.refresh(new Error('offline'));
  assert.deepEqual(b.active(), ['Event 1']);
  assert.equal(b.pendingRequestTimers(), 0);
});

test('a stalled request aborts and the next refresh can recover', async () => {
  const b = await browser(signal => new Promise((_, reject) => {
    signal.addEventListener('abort', () => reject(new Error('aborted')), { once: true });
  }));
  assert.equal(b.requests.length, 1);
  assert.equal(b.pendingRequestTimers(), 1);
  await b.expireRequest();
  assert.equal(b.requests[0].signal.aborted, true);
  assert.equal(b.pendingRequestTimers(), 0);
  assert.deepEqual(b.active(), []);
  await b.refresh([event(1)]);
  assert.deepEqual(b.active(), ['Event 1']);
  assert.equal(b.requests.length, 2);
  assert.equal(b.requests[1].signal.aborted, false);
  assert.notEqual(b.requests[1].signal, b.requests[0].signal);
});

test('browser rotates uncached upcoming flyers and excludes past events in Denver', async () => {
  const b = await browser([event(0, '2026-09-11'), event(1), event(2, '2026-10-10')]);
  assert.deepEqual(b.active(), ['Event 1']);
  b.rotate();
  assert.deepEqual(b.active(), ['Event 2']);
  b.finishFade();
  assert.equal(b.elementCount(), 1);
  b.rotate();
  assert.deepEqual(b.active(), ['Event 1']);
  b.advance('2026-09-13T06:00:00Z');
  b.rotate();
  assert.deepEqual(b.active(), ['Event 2']);
});

test('browser preserves loaded flyers on failure but still expires them offline', async () => {
  const b = await browser([event(1)]);
  await b.refresh(new Error('offline'));
  assert.deepEqual(b.active(), ['Event 1']);
  b.advance('2026-09-13T06:00:00Z');
  b.rotate();
  assert.deepEqual(b.active(), []);
  b.finishFade();
  assert.equal(b.elementCount(), 0);
  await b.refresh([event(2, '2026-10-10')]);
  assert.deepEqual(b.active(), ['Event 2']);
  await b.refresh([]);
  assert.deepEqual(b.active(), []);
});

test('refresh picks up changed flyers, skips broken new images, and holds a single slide', async () => {
  const b = await browser([event(1)]);
  b.rotate();
  assert.deepEqual(b.active(), ['Event 1']);
  b.broken.add(event(2).image);
  await b.refresh([event(1), event(2)]);
  b.rotate();
  assert.deepEqual(b.active(), ['Event 1']);
  const replacement = { ...event(1), title: 'Updated event', image: 'https://example.com/new.jpg' };
  b.broken.add(replacement.image);
  await b.refresh([replacement]);
  assert.deepEqual(b.active(), ['Event 1']);
  b.broken.delete(replacement.image);
  await b.refresh([replacement]);
  assert.deepEqual(b.active(), ['Updated event']);
});

test('an initially unavailable feed stays black and recovers on refresh', async () => {
  const b = await browser(new Error('offline'));
  assert.deepEqual(b.active(), []);
  await b.refresh([event(1)]);
  assert.deepEqual(b.active(), ['Event 1']);
});
