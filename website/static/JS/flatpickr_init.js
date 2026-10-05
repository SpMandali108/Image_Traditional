/**
 * Image Traditional - Modern Plain Date Picker Initializer
 * Replaces segmented native browser date inputs with clean plain fields
 * and opens an elegant custom calendar on click.
 */
(function(window) {
  'use strict';

  function attachFooter(instance) {
    if (!instance || !instance.calendarContainer) return;
    if (instance.calendarContainer.querySelector('.flatpickr-footer-bar')) return;

    const footer = document.createElement('div');
    footer.className = 'flatpickr-footer-bar';
    footer.innerHTML = `
      <button type="button" class="fp-btn-today">Today</button>
      <button type="button" class="fp-btn-clear">Clear</button>
      <button type="button" class="fp-btn-close">Done</button>
    `;

    footer.querySelector('.fp-btn-today').addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      instance.setDate(new Date(), true);
    });

    footer.querySelector('.fp-btn-clear').addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      instance.clear();
      if (typeof instance.config.onChange === 'function') {
        instance.config.onChange([], '', instance);
      }
    });

    footer.querySelector('.fp-btn-close').addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      instance.close();
    });

    instance.calendarContainer.appendChild(footer);
  }

  function initPlainDatePicker(target, customOpts) {
    if (typeof flatpickr === 'undefined') {
      console.warn('Flatpickr is not loaded yet.');
      return null;
    }

    const el = typeof target === 'string' ? document.querySelector(target) : target;
    if (!el) return null;

    const opts = customOpts || {};
    const defaultAltClass = el.classList.contains('form-control-sm')
      ? 'form-control form-control-sm it-plain-date-input date-picker-alt-input'
      : 'form-control it-plain-date-input date-picker-alt-input';

    const config = {
      dateFormat: opts.dateFormat || 'Y-m-d',
      altInput: true,
      altFormat: opts.altFormat || 'd-m-Y',
      altInputClass: opts.altInputClass || defaultAltClass,
      allowInput: false,
      disableMobile: true, // Prevents mobile browsers from switching to native segmented dd/mm/yy input
      defaultDate: opts.defaultDate || el.value || null,
      onReady: function(selectedDates, dateStr, instance) {
        attachFooter(instance);
        if (typeof opts.onReady === 'function') {
          opts.onReady(selectedDates, dateStr, instance);
        }
      },
      onOpen: function(selectedDates, dateStr, instance) {
        attachFooter(instance);
        if (typeof opts.onOpen === 'function') {
          opts.onOpen(selectedDates, dateStr, instance);
        }
      },
      onChange: function(selectedDates, dateStr, instance) {
        if (typeof opts.onChange === 'function') {
          opts.onChange(selectedDates, dateStr, instance);
        }
        // Also dispatch standard change event on original element
        try {
          el.dispatchEvent(new Event('change', { bubbles: true }));
        } catch(e){}
      }
    };

    if (opts.minDate) config.minDate = opts.minDate;
    if (opts.maxDate) config.maxDate = opts.maxDate;

    const fp = flatpickr(el, config);
    el._flatpickrInstance = fp;

    // Attach click handler to trigger button/icon if provided
    if (opts.triggerBtn) {
      const btn = typeof opts.triggerBtn === 'string' ? document.querySelector(opts.triggerBtn) : opts.triggerBtn;
      if (btn) {
        btn.addEventListener('click', function(e) {
          e.preventDefault();
          fp.open();
        });
      }
    }

    return fp;
  }

  window.initPlainDatePicker = initPlainDatePicker;
})(window);
