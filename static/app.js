/* ─── PSDSARC SHARED JS ─── */

// ── Tab switching ──
function initTabs() {
  document.querySelectorAll('[data-tab-group]').forEach(group => {
    const groupName = group.dataset.tabGroup;
    const tabs = group.querySelectorAll('[data-tab]');
    const panels = document.querySelectorAll(`[data-tab-panel="${groupName}"]`);

    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        tabs.forEach(t => t.classList.remove('active'));
        panels.forEach(p => p.classList.remove('active'));
        tab.classList.add('active');
        const target = document.querySelector(`[data-tab-panel="${groupName}"][data-panel="${tab.dataset.tab}"]`);
        if (target) target.classList.add('active');
      });
    });
  });
}

// ── Accordion ──
function initAccordion() {
  document.querySelectorAll('.accordion-header').forEach(header => {
    header.addEventListener('click', () => {
      const item = header.closest('.accordion-item');
      const isOpen = item.classList.contains('open');
      // Close all
      document.querySelectorAll('.accordion-item').forEach(i => i.classList.remove('open'));
      // Open clicked if it was closed
      if (!isOpen) item.classList.add('open');
    });
  });
  // Open first by default
  const first = document.querySelector('.accordion-item');
  if (first) first.classList.add('open');
}

// ── Select cards ──
function initSelectCards() {
  document.querySelectorAll('[data-select-group]').forEach(group => {
    const groupName = group.dataset.selectGroup;
    const cards = document.querySelectorAll(`[data-select="${groupName}"]`);
    cards.forEach(card => {
      card.addEventListener('click', () => {
        cards.forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');
      });
    });
  });
}

// ── Input method toggle ──
function initInputMethod() {
  const cards = document.querySelectorAll('.input-method-card');
  cards.forEach(card => {
    card.addEventListener('click', () => {
      cards.forEach(c => c.classList.remove('selected'));
      card.classList.add('selected');
    });
  });
}

// ── Password toggle ──
function initPasswordToggle() {
  document.querySelectorAll('[data-pw-toggle]').forEach(btn => {
    btn.addEventListener('click', () => {
      const input = btn.closest('.input-wrap').querySelector('input');
      if (!input) return;
      if (input.type === 'password') {
        input.type = 'text';
        btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/></svg>`;
      } else {
        input.type = 'password';
        btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`;
      }
    });
  });
}

// ── Login tabs ──
function initLoginTabs() {
  const tabs = document.querySelectorAll('.login-tab');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
    });
  });
}

// ── Settings nav ──
function initSettingsNav() {
  const items = document.querySelectorAll('.settings-nav-item');
  items.forEach(item => {
    item.addEventListener('click', () => {
      items.forEach(i => i.classList.remove('active'));
      item.classList.add('active');
    });
  });
}

// ── Active nav link based on page ──
function initNavActive() {
  const page = document.body.dataset.page;
  document.querySelectorAll('.nav-link').forEach(link => {
    if (link.dataset.page === page) link.classList.add('active');
  });
}

// ── Init all ──
document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initAccordion();
  initSelectCards();
  initInputMethod();
  initPasswordToggle();
  initLoginTabs();
  initSettingsNav();
  initNavActive();
});
