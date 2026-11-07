/* Invoice preview zoom and OCR review form behaviour. */
(function () {
  'use strict';
  document.addEventListener('DOMContentLoaded', () => {
    const viewer = document.getElementById('doc-viewer');
    if (viewer) initViewer(viewer);
    const form = document.getElementById('review-form');
    if (form) initReview(form);
  });

  function initViewer(viewer) {
    const image = viewer.querySelector('img');
    let zoom = 1;
    const apply = () => {
      image.style.width = (zoom * 100) + '%';
      viewer.querySelector('[data-zoom-level]').textContent = Math.round(zoom * 100) + '%';
    };
    const setZoom = next => { zoom = Math.min(4, Math.max(0.5, next)); apply(); };
    viewer.querySelector('[data-zoom-in]').addEventListener('click', () => setZoom(zoom + 0.25));
    viewer.querySelector('[data-zoom-out]').addEventListener('click', () => setZoom(zoom - 0.25));
    viewer.querySelector('[data-zoom-fit]').addEventListener('click', () => setZoom(1));
    viewer.querySelector('.doc-scroll').addEventListener('wheel', e => {
      if (e.ctrlKey) { e.preventDefault(); setZoom(zoom + (e.deltaY < 0 ? 0.1 : -0.1)); }
    }, { passive: false });

    const pager = viewer.querySelector('[data-pager]');
    if (pager) {
      let page = 1;
      const base = image.dataset.src;
      const label = pager.querySelector('[data-page]');
      const go = next => {
        page = next;
        image.src = base + '?page=' + page;
        label.textContent = 'Page ' + page;
      };
      pager.querySelector('[data-prev]').addEventListener('click', () => { if (page > 1) go(page - 1); });
      pager.querySelector('[data-next]').addEventListener('click', () => go(page + 1));
    }
  }

  function initReview(form) {
    const accept = document.getElementById('accept-all');
    if (accept) {
      accept.addEventListener('click', () => {
        const values = JSON.parse(accept.dataset.values);
        Object.keys(values).forEach(name => {
          if (values[name] === null) return;
          const field = form.elements[name];
          if (field) field.value = values[name];
        });
        recalc();
        window.KTAP.toast('OCR values applied. Check the cost centre and category, then submit.', 'info');
      });
    }

    const names = ['final_taxable_amount', 'final_cgst', 'final_sgst', 'final_igst'];
    const total = form.elements.final_total_amount;
    const hint = document.getElementById('arith-hint');
    const number = el => parseFloat(String(el.value).replace(/,/g, '')) || 0;
    function recalc() {
      if (!hint) return;
      const sum = names.reduce((acc, n) => acc + number(form.elements[n]), 0);
      const diff = Math.abs(sum - number(total));
      hint.textContent = 'Taxable + taxes = ' + sum.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) +
        (diff <= 1 ? ' — matches the total' : ' — differs from the total by ' + diff.toFixed(2));
      hint.className = 'arith-hint ' + (diff <= 1 ? 'ok' : 'bad');
    }
    names.concat('final_total_amount').forEach(n => form.elements[n].addEventListener('input', recalc));
    recalc();

    const table = document.getElementById('line-items');
    const add = document.getElementById('add-line');
    if (table && add) {
      const template = document.getElementById('line-template');
      add.addEventListener('click', () => table.querySelector('tbody').appendChild(template.content.cloneNode(true)));
      table.addEventListener('click', e => {
        if (e.target.matches('[data-remove-line]')) e.target.closest('tr').remove();
      });
    }
  }
})();
