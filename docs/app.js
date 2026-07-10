const DATA_URL = 'data.json';
const POLL_INTERVAL = 60000;
const TICK_INTERVAL = 30000;

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
  if (h > 0) return `${h}ч ${m}м`;
  if (m > 0) return `${m}м`;
  const s = Math.floor((diff % 60000) / 1000);
  return `${s}с`;
}

function formatMsk(validUntil) {
  if (!validUntil) return '';
  const d = new Date(validUntil);
  const msk = new Date(d.getTime() + 3 * 3600000);
  return msk.toISOString().replace('T', ' ').slice(0, 16) + ' MSK';
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
  const valid = data.filter(d => d.is_valid);
  const expired = data.filter(d => !d.is_valid);

  container.innerHTML = '';

  [...valid, ...expired].forEach(d => {
    const cls = d.is_valid ? 'valid' : 'expired';
    const countdown = formatCountdown(d.valid_until);
    const timerCls = timerClass(d.valid_until);

    const card = document.createElement('div');
    card.className = `card ${cls}`;
    card.innerHTML = `
      <div class="card-icon">💿</div>
      <div class="card-info">
        <div class="card-title">ISO-образ ${versionLabel(d.version)} (${d.version.build || '?'})</div>
        <div class="card-meta">
          <span>🔤 ${d.version.lang || '?'}</span>
          <span>🖥 ${d.version.arch || '?'}</span>
          <span>📦 ${formatSize(d.size_bytes) || '?'}</span>
          <span>👤 ${d.author || '?'}</span>
        </div>
      </div>
      <div class="card-timer ${timerCls}">${countdown || (d.is_valid ? 'скоро' : 'истекла')}${d.is_valid && d.valid_until ? '<br><span class="timer-msk">до ' + formatMsk(d.valid_until) + '</span>' : ''}</div>
      <a class="btn btn-download ${cls}" href="${d.is_valid ? d.iso_url : '#'}"
         ${d.is_valid ? 'target="_blank" rel="noopener"' : ''}>
        ${d.is_valid ? 'Скачать' : 'Недоступна'}
      </a>
    `;
    container.appendChild(card);
  });
}

function updateStatus() {
  const valid = data.filter(d => d.is_valid);
  document.getElementById('valid-count').textContent =
    `Доступно ссылок: ${valid.length} / ${data.length}`;
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
      timerEl.textContent = 'истекла';
      timerEl.className = 'card-timer timer-red';
      return;
    }

    const countdown = formatCountdown(d.valid_until);
    timerEl.className = `card-timer ${timerClass(d.valid_until)}`;
    if (countdown) {
      timerEl.textContent = countdown;
    } else {
      timerEl.textContent = 'скоро';
      timerEl.className = 'card-timer timer-red';
      d.is_valid = false;
      downloadBtn.className = 'btn btn-download expired';
      downloadBtn.textContent = 'Недоступна';
      downloadBtn.removeAttribute('target');
      downloadBtn.removeAttribute('rel');
      downloadBtn.href = '#';
    }
  });
}

async function fetchData() {
  try {
    const resp = await fetch(DATA_URL + '?_=' + Date.now());
    data = await resp.json();
    renderCards();
    updateStatus();
    document.getElementById('last-checked').textContent =
      `Обновлено: ${new Date().toLocaleTimeString('ru-RU')}`;
  } catch (e) {
    document.getElementById('last-checked').textContent = 'Ошибка загрузки данных';
    console.error(e);
  }
}

function showRequestModal() {
  const lang = navigator.language.startsWith('ru') ? 'Russian' : 'English';
  const text = `Здравствуйте. Не могу скачать официальный ISO-образ Windows — Microsoft блокирует загрузку из России. Сгенерируйте, пожалуйста, прямую ссылку на Windows 10/11 ${lang} x64.

Спасибо.`;
  document.getElementById('request-text').value = text;
  document.getElementById('request-modal').classList.remove('hidden');
}

function hideRequestModal() {
  document.getElementById('request-modal').classList.add('hidden');
}

function copyRequest() {
  const ta = document.getElementById('request-text');
  ta.select();
  navigator.clipboard.writeText(ta.value).then(() => {
    window.open('https://learn.microsoft.com/ru-ru/answers/tags/977/windows-home-windows-10-platform-install-upgrade', '_blank');
    hideRequestModal();
  }).catch(() => {
    document.execCommand('copy');
    window.open('https://learn.microsoft.com/ru-ru/answers/tags/977/windows-home-windows-10-platform-install-upgrade', '_blank');
    hideRequestModal();
  });
}

fetchData();
setInterval(fetchData, POLL_INTERVAL);
setInterval(updateTimers, TICK_INTERVAL);
