'use strict';

// Read-only enhancements. Nothing here can change the negative verdict or upload.
document.querySelectorAll('[data-copy]').forEach(button => {
  button.addEventListener('click', async () => {
    const text = document.getElementById(button.dataset.copy)?.textContent || '';
    const feedback = document.getElementById('copy-feedback');
    try {
      if (!navigator.clipboard || !window.isSecureContext) throw new Error('Clipboard unavailable');
      await navigator.clipboard.writeText(text);
      if (feedback) feedback.textContent = 'Copied. Research identification only—not authorization to submit.';
    } catch {
      if (feedback) feedback.textContent = 'Clipboard unavailable; the text above remains selectable.';
    }
  });
});

document.querySelectorAll('[data-filter]').forEach(input => {
  const table = document.getElementById(input.dataset.filter);
  if (!table) return;
  const rows = [...table.querySelectorAll('[data-search-row]')];
  const count = document.getElementById('filter-count');
  const update = () => {
    const q = input.value.trim().toLowerCase();
    let visible = 0;
    rows.forEach(row => {
      row.hidden = !row.textContent.toLowerCase().includes(q);
      if (!row.hidden) visible++;
    });
    if (count) count.textContent = `${visible} of ${rows.length} repositories`;
  };
  input.addEventListener('input', update);
  update();
});

(async function sourceFeed() {
  const states = document.querySelectorAll('[data-feed-state]');
  const details = document.querySelectorAll('[data-feed-detail]');
  const setState = (text, stale) => states.forEach(el => {
    el.textContent = text;
    el.classList.toggle('stale', stale);
  });
  try {
    const response = await fetch('data/feed.json', {cache: 'no-store'});
    if (!response.ok) throw new Error('feed unavailable');
    const feed = await response.json();
    const last = new Date(feed.last_attempt_utc);
    if (!Number.isFinite(last.getTime())) throw new Error('invalid feed time');
    const ageHours = (Date.now() - last.getTime()) / 3600000;
    const stale = ageHours > 24 || ageHours < -1;
    if (!Array.isArray(feed.checks) || feed.checks.length === 0) throw new Error('missing source checks');
    const failures = feed.checks.filter(c => !c.transport_ok).length;
    const stamp = last.toISOString().replace('T', ' ').slice(0, 16) + ' UTC';
    setState(stale ? `Source feed stale · ${stamp}` :
      failures ? `Source check ${stamp} · ${failures} transport limitations` : `Source check ${stamp}`, stale || failures > 0);
    details.forEach(el => {
      el.textContent = `Last automated attempt: ${stamp}. ${failures} URL transport checks failed or required login. Content review and submission receipts are separate; this feed does not authorize a slot.`;
    });
    const observation = feed.public_leaderboard_observation;
    if (observation && observation.source_url === 'https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/' &&
        observation.evidence_class === 'PUBLIC-LEADERBOARD-OBSERVATION' && observation.artifact_submission_receipt === false &&
        typeof observation.observed_utc === 'string' && typeof observation.value === 'number' && Number.isFinite(observation.value) && observation.value >= 0 && observation.value <= 1) {
      document.querySelectorAll('[data-leaderboard-value]').forEach(el => {
        el.textContent = observation.value.toFixed(4);
        el.title = `Public leaderboard observed ${observation.observed_utc}; not an artifact submission receipt`;
      });
      document.querySelectorAll('[data-leaderboard-observed]').forEach(el => { el.textContent = observation.observed_utc; });
    }
  } catch {
    setState('Source feed unavailable · research snapshot only', true);
    details.forEach(el => { el.textContent = 'The live source-health feed could not be read. The dated research snapshot remains visible; no current submission cap or organizer receipt is inferred.'; });
  }
})();
