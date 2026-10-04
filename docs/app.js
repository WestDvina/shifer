const DATA_URL = 'data.json';
// Canonical single source of truth (same file Rufus-RuBeRoID reads).
// Used as fallback when data.json has no valid link for a key.
const CANONICAL_URL = 'https://raw.githubusercontent.com/WestDvina/rufus-RuBeRoID/main/iso_links.json';
const CANONICAL_KEYS = {
  '10_x64': { os: 'win10', arch: 'x64', build: '22H2' },
  '10_x86': { os: 'win10', arch: 'x86', build: '22H2' },
  '11_x64': { os: 'win11', arch: 'x64', build: '' },
};

function canonicalFallbackEntries(canonical, existing) {
  const out = [];
  if (!canonical || !canonical.links) return out;
  const ttlMs = (canonical.ttl_hours || 22) * 3600000;
  const base = (canonical.published_at || Date.now() / 1000) * 1000;
  for (const [key, meta] of Object.entries(CANONICAL_KEYS)) {
    const url = canonical.links[key];
    if (!url) continue;
    const covered = (existing || []).some(d =>
      d.is_valid && d.version && d.version.os === meta.os && d.version.arch === meta.arch);
    if (covered) continue;
    const m = url.split('?')[0].match(/(2[23456]h2)/i);
    out.push({
      id: '', title: 'Зеркало RuBeRoID', question_url: CANONICAL_URL,
      iso_url: url, author: 'RuBeRoID', author_url: 'https://github.com/WestDvina/rufus-RuBeRoID',
      version: { os: meta.os, build: m ? m[1].toUpperCase() : meta.build, lang: 'Russian', arch: meta.arch },
      is_valid: true, size_bytes: 0,
      checked_at: new Date().toISOString(),
      valid_until: new Date(base + ttlMs).toISOString(),
    });
  }
  return out;
}
const POLL_INTERVAL = 60000;
const TICK_INTERVAL = 1000;

let data = [];

function formatSize(bytes) {
  if (!bytes) return '';
  const gb = bytes / (1024 * 1024 * 1024);
  if (gb >= 1) return gb.toFixed(1) + ' GB';
  const mb = bytes / (1024 * 1024);
  return mb.toFixed(0) + ' MB';
}

function formatCountdown(validUntil) {
  if (!validUntil) return null;
  const diff = new Date(validUntil) - Date.now();
  if (diff <= 0) return null;
  const h = Math.floor(diff / 3600000);
  const m = Math.floor((diff % 3600000) / 60000);
  const s = Math.floor((diff % 60000) / 1000);
  if (h > 0) return `${h}ч ${m}м`;
  if (diff < 300000) return `${m}м ${s}с`;
  if (m > 0) return `${m}м`;
  return `${s}с`;
}

function formatMsk(validUntil) {
  if (!validUntil) return '';
  const d = new Date(validUntil);
  const msk = new Date(d.getTime() + 3 * 3600000);
  const day = String(msk.getUTCDate()).padStart(2, '0');
  const month = String(msk.getUTCMonth() + 1).padStart(2, '0');
  const year = msk.getUTCFullYear();
  const hh = String(msk.getUTCHours()).padStart(2, '0');
  const mm = String(msk.getUTCMinutes()).padStart(2, '0');
  return `${day}-${month}-${year} ${hh}:${mm} MSK`;
}

function timerClass(validUntil) {
  if (!validUntil) return 'timer-red';
  const diff = new Date(validUntil) - Date.now();
  if (diff <= 0) return 'timer-red';
  if (diff < 3600000) return 'timer-orange';
  return 'timer-green';
}

function versionLabel(v) {
  if (v.os === 'win10') return 'Windows 10';
  if (v.os === 'win11') return 'Windows 11';
  return 'Windows';
}

function renderCards() {
  const container = document.getElementById('cards-container');
  const oneHourAgo = Date.now() - 3600000;

  const filtered = data.filter(d => {
    if (d.is_valid) return true;
    if (!d.valid_until) return false;
    return new Date(d.valid_until).getTime() > oneHourAgo;
  });

  const valid = filtered.filter(d => d.is_valid);
  const expired = filtered.filter(d => !d.is_valid);

  container.innerHTML = '';

  [...valid, ...expired].forEach(d => {
    const cls = d.is_valid ? 'valid' : 'expired';
    const countdown = formatCountdown(d.valid_until);
    const timerCls = timerClass(d.valid_until);

    const card = document.createElement('div');
    const noTimer = d.is_valid && !countdown;
    card.className = `card ${noTimer ? 'no-timer' : cls}`;
    card.innerHTML = `
      <div class="card-icon">💿</div>
      <div class="card-info">
        <div class="card-title">ISO-образ ${versionLabel(d.version)} (${d.version.build || '?'})</div>
        <div class="card-meta">
          <span>🔤 ${d.version.lang || '?'}</span>
          <span>🖥 ${d.version.arch || '?'}</span>
          <span>📦 ${formatSize(d.size_bytes) || '?'}</span>
          <span>👤 ${d.author_url ? `<a href="${d.author_url}" target="_blank" rel="nofollow noopener">${d.author || '?'}</a>` : (d.author || '?')}</span>
        </div>
      </div>
      <div class="card-timer ${timerCls}">${countdown ? `<span class="timer-countdown">${countdown}</span><br><span class="timer-msk">до ${formatMsk(d.valid_until)}</span><span class="timer-help" data-tip="Время до конца действия ссылки">?</span>` : (noTimer ? '' : 'истекла')}</div>
      <a class="btn btn-download ${noTimer ? 'expired' : cls}" href="${noTimer ? '#' : (d.is_valid ? d.iso_url : '#')}"
         ${noTimer || !d.is_valid ? '' : 'target="_blank" rel="noopener"'} ${d.is_valid && countdown ? 'onclick="ym(110712171,\'reachGoal\',\'download\')"' : ''}>
        ${noTimer ? 'Истёк срок' : (d.is_valid ? 'Скачать' : 'Недоступна')}
      </a>
    `;
    container.appendChild(card);
  });

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">🔗</div>
        <h2 class="empty-title">Нет активных ссылок</h2>
        <p class="empty-desc">Все ссылки истекли. Новые появляются, когда кто-то запрашивает образ в Microsoft Q&A.</p>
        <button class="btn btn-empty" onclick="showRequestModal()">Запросить ISO</button>
        <p class="empty-hint">Страница проверяет наличие ссылок каждую минуту</p>
      </div>
    `;
  }
}

function updateStatus() {
  const oneHourAgo = Date.now() - 3600000;
  const visible = data.filter(d => d.is_valid || (d.valid_until && new Date(d.valid_until).getTime() > oneHourAgo));
  const valid = visible.filter(d => d.is_valid);
  document.getElementById('valid-count').textContent =
    `Доступно ссылок: ${valid.length} / ${visible.length}`;
}

function updateTimers() {
  document.querySelectorAll('.card').forEach(card => {
    const timerEl = card.querySelector('.card-timer');
    if (!timerEl) return;
    const downloadBtn = card.querySelector('.btn-download');
    if (!downloadBtn) return;

    const isoUrl = downloadBtn.getAttribute('href');
    const d = data.find(item => item.iso_url === isoUrl);
    if (!d) return;

    if (!d.is_valid) {
      timerEl.innerHTML = 'истекла';
      timerEl.className = 'card-timer timer-red';
      return;
    }

    const countdown = formatCountdown(d.valid_until);
    timerEl.className = `card-timer ${timerClass(d.valid_until)}`;
    if (countdown) {
      const cdSpan = timerEl.querySelector('.timer-countdown');
      const mskSpan = timerEl.querySelector('.timer-msk');
      if (cdSpan) cdSpan.textContent = countdown;
      if (mskSpan) mskSpan.textContent = 'до ' + formatMsk(d.valid_until);
    } else {
      timerEl.innerHTML = '';
      card.classList.add('no-timer');
      card.classList.remove('valid', 'expired');
    }
  });
}

async function fetchData() {
  try {
    const resp = await fetch(DATA_URL + '?_=' + Date.now());
    data = await resp.json();
    try {
      const cResp = await fetch(CANONICAL_URL + '?_=' + Date.now());
      if (cResp.ok) {
        const canonical = await cResp.json();
        data = data.concat(canonicalFallbackEntries(canonical, data));
      }
    } catch (e2) { console.error('canonical fallback failed', e2); }
    renderCards();
    updateStatus();
    document.getElementById('last-checked').textContent =
      `Обновлено: ${new Date().toLocaleTimeString('ru-RU')}`;
  } catch (e) {
    document.getElementById('last-checked').textContent = 'Ошибка загрузки данных';
    console.error(e);
  }
}

const ASK_URL = 'https://learn.microsoft.com/ru-ru/answers/questions/ask/?id=aHR0cHM6Ly9taWNyb3NvZnQtZGV2cmVsLnBvb2xwYXJ0eS5iaXovUW5BQ29tcG91bmQvNGM1MmRmZjUtMjE1Ni00MmMxLWE3ODEtMWQ2NDI5ZDg5YTE0&styleGuideLabel=Windows%20%D0%B4%D0%BB%D1%8F%20%D0%B4%D0%BE%D0%BC%D0%B0%20|%20Windows%2010%20|%20%D0%A3%D1%81%D1%82%D0%B0%D0%BD%D0%BE%D0%B2%D0%BA%D0%B0%20%D0%B8%20%D0%BE%D0%B1%D0%BD%D0%BE%D0%B2%D0%BB%D0%B5%D0%BD%D0%B8%D0%B5';

function showRequestModal() {
  document.getElementById('request-form-view').classList.remove('hidden');
  document.getElementById('request-result-view').classList.add('hidden');
  document.getElementById('request-modal').classList.remove('hidden');
  document.documentElement.style.overflow = 'hidden';
  ym(110712171, 'reachGoal', 'request-iso');
}

function hideRequestModal() {
  document.getElementById('request-modal').classList.add('hidden');
  document.documentElement.style.overflow = '';
}

function showFaqModal() {
  document.getElementById('faq-modal').classList.remove('hidden');
  document.documentElement.style.overflow = 'hidden';
}

function hideFaqModal() {
  document.getElementById('faq-modal').classList.add('hidden');
  document.documentElement.style.overflow = '';
}

function onOsChange() {
  const os = document.querySelector('input[name="os"]:checked').value;
  document.getElementById('arch-group').classList.toggle('hidden', os === 'win11');
}

function generateRequest() {
  const os = document.querySelector('input[name="os"]:checked').value;
  const arch = document.querySelector('input[name="arch"]:checked')?.value || 'x64';

  const osLabel = os === 'win10' ? 'Windows 10' : 'Windows 11';
  const version = os === 'win10' ? '22H2' : '25H2';
  const archLabel = os === 'win11' ? '' : (arch === 'x64' ? '64-bit (x64)' : '32-bit (x86)');
  const archSuffix = os === 'win11' ? 'x64' : arch;

  const exampleTitle = `Please provide a link to the Windows ${os === 'win10' ? '10' : '11'} ISO image`;
  document.getElementById('example-title').textContent = exampleTitle;

  const text = `Здравствуйте!

Я нахожусь в России и не могу скачать ISO-образ ${osLabel} с официального сайта из-за региональных ограничений. Официальная страница загрузки и Media Creation Tool недоступны.

Пожалуйста, предоставьте прямую временную ссылку для скачивания официального ISO-образа со следующими параметрами:
- Версия: ${osLabel} ${version}
- Язык: Русский (ru-RU)
- Архитектура: ${archLabel || '64-bit (x64)'}
- Редакция: Multi-Edition (Home/Pro)

Благодарю!`;

  document.getElementById('request-text').value = text;
  document.getElementById('request-form-view').classList.add('hidden');
  document.getElementById('request-result-view').classList.remove('hidden');
}

function backToForm() {
  document.getElementById('request-form-view').classList.remove('hidden');
  document.getElementById('request-result-view').classList.add('hidden');
}

function copyAndOpenAsk() {
  const ta = document.getElementById('request-text');
  ta.select();
  navigator.clipboard.writeText(ta.value).then(() => {
    window.open(ASK_URL, '_blank');
    hideRequestModal();
  }).catch(() => {
    document.execCommand('copy');
    window.open(ASK_URL, '_blank');
    hideRequestModal();
  });
}

fetchData();
setInterval(fetchData, POLL_INTERVAL);
setInterval(updateTimers, TICK_INTERVAL);

(function() {
  var w = window, d = document;
  var s = d.createElement('script');
  s.async = true;
  s.src = 'https://mc.yandex.ru/metrika/tag.js?id=110712171';
  var n = d.getElementsByTagName('script')[0];
  n.parentNode.insertBefore(s, n);
  w.ym = w.ym || function() { (w.ym.a = w.ym.a || []).push(arguments); };
  w.ym.l = 1 * new Date();
  w.ym(110712171, 'init', {
    webvisor: true,
    clickmap: true,
    accurateTrackBounce: true,
    trackLinks: true
  });
})();
