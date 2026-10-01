/**
 * ============================================================================
 * Image Traditional - Rental Date Picker & Availability Modal
 * 
 * Strict Privacy & Ephemeral State Rules:
 * - Selected date is ONLY for the current availability check or inquiry.
 * - ZERO storage: No MongoDB, no session, no localStorage, no persistence.
 * - Fully timezone-shift proof: Uses explicit numeric date components.
 * - Dynamic: Automatically adapts to whichever costume the customer clicked.
 * - Kediya & Choli: Check Availability -> Backend Check -> Popup Result -> Inquire on WhatsApp
 * - Fancy: Traditional inquiry via WhatsApp.
 * ============================================================================
 */

(function () {
  'use strict';

  // Shared Reference-Counting Background Scroll Locker (iOS Safari safe)
  const ModalScrollLock = {
    activeCount: 0,
    savedScrollY: 0,
    lock: function () {
      this.activeCount++;
      if (this.activeCount === 1) {
        this.savedScrollY = window.pageYOffset || document.documentElement.scrollTop || document.body.scrollTop || 0;
        document.body.style.position = 'fixed';
        document.body.style.top = `-${this.savedScrollY}px`;
        document.body.style.left = '0';
        document.body.style.right = '0';
        document.body.style.width = '100%';
        document.body.style.overflow = 'hidden';
        document.documentElement.classList.add('it-modal-locked');
      }
    },
    unlock: function () {
      this.activeCount = Math.max(0, this.activeCount - 1);
      if (this.activeCount === 0) {
        const topVal = document.body.style.top;
        const scrollY = topVal ? Math.abs(parseInt(topVal, 10)) : this.savedScrollY;
        document.body.style.position = '';
        document.body.style.top = '';
        document.body.style.left = '';
        document.body.style.right = '';
        document.body.style.width = '';
        document.body.style.overflow = '';
        document.documentElement.classList.remove('it-modal-locked');
        window.scrollTo(0, scrollY);
      }
    },
    forceUnlock: function () {
      this.activeCount = 0;
      const topVal = document.body.style.top;
      const scrollY = topVal ? Math.abs(parseInt(topVal, 10)) : this.savedScrollY;
      document.body.style.position = '';
      document.body.style.top = '';
      document.body.style.left = '';
      document.body.style.right = '';
      document.body.style.width = '';
      document.body.style.overflow = '';
      document.documentElement.classList.remove('it-modal-locked');
      window.scrollTo(0, scrollY);
    }
  };

  window.ModalScrollLock = ModalScrollLock;

  // In-memory ephemeral state (NEVER persisted)
  let activeInquiry = null; // { mode, costumeName, costumeCode, costumePrice, costumeImage, category, subcategory, phone }
  let selectedRentalDate = null; // { year, month, day }
  let lastAvailabilityResult = null; // { available, product_code, price, ... }
  let viewYear = null;
  let viewMonth = null; // 0-indexed (0 = Jan, 11 = Dec)
  let isChecking = false;

  const MONTH_NAMES = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];

  /**
   * Helper: Get current local date parts
   */
  function getTodayParts() {
    const now = new Date();
    return {
      year: now.getFullYear(),
      month: now.getMonth(),
      day: now.getDate()
    };
  }

  /**
   * Helper: Check if a given date is strictly in the past
   */
  function isDatePast(year, month, day) {
    const today = getTodayParts();
    if (year < today.year) return true;
    if (year > today.year) return false;
    if (month < today.month) return true;
    if (month > today.month) return false;
    return day < today.day;
  }

  /**
   * Helper: Check if a date matches today
   */
  function isDateToday(year, month, day) {
    const today = getTodayParts();
    return year === today.year && month === today.month && day === today.day;
  }

  /**
   * Helper: Check if a date is currently selected in the calendar
   */
  function isDateSelected(year, month, day) {
    if (!selectedRentalDate) return false;
    return (
      selectedRentalDate.year === year &&
      selectedRentalDate.month === month &&
      selectedRentalDate.day === day
    );
  }

  /**
   * Format date strictly as DD-MM-YYYY (immune to UTC/timezone offset shifts)
   */
  function formatAsDDMMYYYY(dateParts) {
    if (!dateParts) return '';
    const dd = String(dateParts.day).padStart(2, '0');
    const mm = String(dateParts.month + 1).padStart(2, '0');
    const yyyy = dateParts.year;
    return `${dd}-${mm}-${yyyy}`;
  }

  /**
   * Format price display string dynamically
   */
  function formatPriceString(priceVal) {
    if (priceVal !== undefined && priceVal !== null && String(priceVal).trim() !== '' && String(priceVal).trim() !== 'null') {
      const p = String(priceVal).trim();
      return p.startsWith('₹') ? p : `₹${p}`;
    }
    return 'Price on Request';
  }

  /**
   * Construct absolute public URL for costume image
   */
  function resolvePublicImageUrl(rawImg, category) {
    if (!rawImg) {
      return `${window.location.origin}/static/Home_Img/favicon.png`;
    }
    const cleanImg = String(rawImg).trim();
    if (cleanImg.startsWith('http://') || cleanImg.startsWith('https://')) {
      return cleanImg;
    }
    if (cleanImg.startsWith('/')) {
      return `${window.location.origin}${cleanImg}`;
    }
    const subFolder = (category === 'Kediya') ? 'Kediya' : ((category === 'Choli') ? 'Choli' : '');
    if (subFolder) {
      return `${window.location.origin}/static/${subFolder}/${cleanImg}`;
    }
    return `${window.location.origin}/${cleanImg}`;
  }

  /**
   * Render calendar days grid for viewYear and viewMonth
   */
  function renderCalendarGrid() {
    const grid = document.getElementById('itDaysGrid');
    const monthYearDisplay = document.getElementById('itMonthYearDisplay');
    const prevBtn = document.getElementById('itPrevMonthBtn');

    if (!grid || !monthYearDisplay) return;

    monthYearDisplay.textContent = `${MONTH_NAMES[viewMonth]} ${viewYear}`;

    // Disable prev button if view is currently at the current month & year
    const today = getTodayParts();
    const isCurrentOrPastMonth =
      viewYear < today.year || (viewYear === today.year && viewMonth <= today.month);

    if (prevBtn) {
      prevBtn.disabled = isCurrentOrPastMonth;
      prevBtn.classList.toggle('disabled', isCurrentOrPastMonth);
    }

    grid.innerHTML = '';

    // Day of the week for the 1st of this month (0 = Sun, 1 = Mon, ..., 6 = Sat)
    const firstDayIndex = new Date(viewYear, viewMonth, 1).getDay();
    // Number of days in current month
    const totalDaysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();

    // Render leading empty spacer cells
    for (let i = 0; i < firstDayIndex; i++) {
      const emptyCell = document.createElement('div');
      emptyCell.className = 'it-day-cell is-empty';
      grid.appendChild(emptyCell);
    }

    // Render active day cells
    for (let day = 1; day <= totalDaysInMonth; day++) {
      const cell = document.createElement('button');
      cell.type = 'button';
      cell.className = 'it-day-cell';
      cell.textContent = day;

      const past = isDatePast(viewYear, viewMonth, day);
      const todayBool = isDateToday(viewYear, viewMonth, day);
      const selectedBool = isDateSelected(viewYear, viewMonth, day);

      if (past) {
        cell.classList.add('is-disabled');
        cell.disabled = true;
        cell.setAttribute('aria-disabled', 'true');
      } else {
        if (todayBool) cell.classList.add('is-today');
        if (selectedBool) cell.classList.add('is-selected');

        const currentDay = day;
        cell.onclick = function () {
          handleDateSelection(viewYear, viewMonth, currentDay);
        };
      }

      grid.appendChild(cell);
    }

    updateSelectionUI();
  }

  /**
   * Handle user clicking a day
   */
  function handleDateSelection(year, month, day) {
    selectedRentalDate = { year: year, month: month, day: day };
    lastAvailabilityResult = null;

    // Reset previous availability check result when a new date is picked
    const resultContainer = document.getElementById('itAvailabilityResult');
    if (resultContainer && activeInquiry && activeInquiry.mode === 'check_availability') {
      resultContainer.style.display = 'none';
      resultContainer.innerHTML = '';
    }

    // When date is changed in check_availability mode, WhatsApp button resets to disabled
    const waBtn = document.getElementById('itWhatsAppInquiryBtn');
    if (waBtn && activeInquiry && activeInquiry.mode === 'check_availability') {
      waBtn.disabled = true;
      waBtn.classList.remove('is-active-wa');
    }

    renderCalendarGrid();
  }

  /**
   * Update bottom preview row and continue button status
   */
  function updateSelectionUI() {
    const previewBox = document.getElementById('itSelectionPreview');
    const previewText = document.getElementById('itPreviewText');
    const actionBtn = document.getElementById('itContinueWaBtn');
    const waBtn = document.getElementById('itWhatsAppInquiryBtn');

    if (selectedRentalDate) {
      const formatted = formatAsDDMMYYYY(selectedRentalDate);
      if (previewText) {
        previewText.innerHTML = `Selected Date: <strong style="color: #f4d35e;">${formatted}</strong>`;
      }
      if (previewBox) {
        previewBox.classList.add('has-selection');
      }

      if (activeInquiry && activeInquiry.mode === 'whatsapp') {
        if (waBtn) {
          waBtn.disabled = false;
          waBtn.classList.add('is-active-wa');
        }
      } else {
        if (actionBtn && !isChecking) {
          actionBtn.disabled = false;
        }
        // In check_availability mode, WhatsApp button stays disabled until check succeeds
        if (waBtn && (!lastAvailabilityResult || lastAvailabilityResult.available !== true)) {
          waBtn.disabled = true;
          waBtn.classList.remove('is-active-wa');
        }
      }
    } else {
      if (previewText) {
        previewText.textContent = 'Please tap a date for your rental';
      }
      if (previewBox) {
        previewBox.classList.remove('has-selection');
      }
      if (actionBtn) {
        actionBtn.disabled = true;
      }
      if (waBtn) {
        waBtn.disabled = true;
        waBtn.classList.remove('is-active-wa');
      }
    }
  }

  /**
   * Month navigation control (prev/next)
   */
  function navigateCalendarMonth(direction) {
    viewMonth += direction;
    if (viewMonth > 11) {
      viewMonth = 0;
      viewYear += 1;
    } else if (viewMonth < 0) {
      viewMonth = 11;
      viewYear -= 1;
    }
    renderCalendarGrid();
  }

  /**
   * Public API: Open Rental Date Picker Modal
   * @param {Object} options - { mode, costumeName, costumeCode, costumePrice, costumeImage, category, subcategory, phone }
   * mode can be 'check_availability' (Kediya/Choli) or 'whatsapp' (Fancy)
   */
  function openRentalDatePicker(options) {
    options = options || {};

    // In-memory dynamic binding
    activeInquiry = {
      mode: options.mode || 'whatsapp',
      costumeName: options.costumeName || 'Costume',
      costumeCode: options.costumeCode || '',
      costumePrice: options.costumePrice || '',
      costumeImage: options.costumeImage || '',
      category: options.category || '',
      subcategory: options.subcategory || '',
      phone: options.phone || '919428610384'
    };

    // ALWAYS reset selection when opened fresh (DO NOT STORE PREVIOUS DATES)
    selectedRentalDate = null;
    lastAvailabilityResult = null;
    isChecking = false;

    const today = getTodayParts();
    viewYear = today.year;
    viewMonth = today.month;

    // Elements
    const title = document.getElementById('itDatepickerTitle');
    const subtitle = document.getElementById('itDatepickerSubtitle');
    const badgeText = document.getElementById('itCostumeBadgeText');
    const actionBtn = document.getElementById('itContinueWaBtn');
    const btnText = document.getElementById('itBtnActionText');
    const btnArrow = document.getElementById('itBtnActionArrow');
    const waInquiryBtn = document.getElementById('itWhatsAppInquiryBtn');
    const resultContainer = document.getElementById('itAvailabilityResult');

    if (resultContainer) {
      resultContainer.style.display = 'none';
      resultContainer.innerHTML = '';
    }

    const catName = activeInquiry.category || 'Costume';
    const codeDisplay = activeInquiry.costumeCode || activeInquiry.costumeName;

    if (activeInquiry.mode === 'check_availability') {
      // Setup UI for Check Availability Mode
      if (title) title.textContent = 'Check Availability';
      if (subtitle) subtitle.textContent = 'Select a rental date to check live availability';
      if (badgeText) badgeText.textContent = `${catName} Code: ${codeDisplay}`;
      
      // Primary Action button: Check Availability
      if (actionBtn) {
        actionBtn.className = 'it-btn-continue btn-gold-theme';
        actionBtn.disabled = true;
        actionBtn.style.display = '';
      }
      if (btnText) btnText.textContent = 'Check Availability';
      if (btnArrow) btnArrow.textContent = '🔍';

      // WhatsApp button in popup: visible from start, neutral disabled until availability is confirmed
      if (waInquiryBtn) {
        waInquiryBtn.style.display = 'inline-flex';
        waInquiryBtn.disabled = true;
        waInquiryBtn.classList.remove('is-active-wa');
      }
    } else {
      // Setup UI for WhatsApp Inquiry Mode (Fancy collection)
      if (title) title.textContent = 'Select Rental Date';
      if (subtitle) subtitle.textContent = 'Choose the required date to inquire about costume availability';
      if (badgeText) {
        let label = activeInquiry.costumeName;
        if (activeInquiry.category === 'Fancy' && activeInquiry.subcategory) {
          label = `${activeInquiry.costumeName} (${activeInquiry.subcategory})`;
        }
        badgeText.textContent = label;
      }
      if (actionBtn) {
        actionBtn.style.display = 'none';
      }

      if (waInquiryBtn) {
        waInquiryBtn.style.display = 'inline-flex';
        waInquiryBtn.disabled = true;
        waInquiryBtn.classList.remove('is-active-wa');
      }
    }

    renderCalendarGrid();

    const modal = document.getElementById('itDatePickerModal');
    if (modal) {
      modal.classList.add('is-active');
      modal.setAttribute('aria-hidden', 'false');
    }

    // Lock background webpage scroll
    ModalScrollLock.lock();
  }

  /**
   * Public API: Close Rental Date Picker Modal
   * Discards ephemeral state and returns cleanly to costume popup
   */
  function closeRentalDatePicker() {
    const modal = document.getElementById('itDatePickerModal');
    if (modal) {
      modal.classList.remove('is-active');
      modal.setAttribute('aria-hidden', 'true');
    }

    // Unlock background webpage scroll
    ModalScrollLock.unlock();

    const resultContainer = document.getElementById('itAvailabilityResult');
    if (resultContainer) {
      resultContainer.style.display = 'none';
      resultContainer.innerHTML = '';
    }

    const waBtn = document.getElementById('itWhatsAppInquiryBtn');
    if (waBtn) {
      waBtn.style.display = 'none';
      waBtn.disabled = true;
      waBtn.classList.remove('is-active-wa');
    }

    // Clean up temporary variables immediately (ZERO persistence)
    activeInquiry = null;
    selectedRentalDate = null;
    lastAvailabilityResult = null;
    isChecking = false;
  }

  /**
   * Dispatch primary modal action based on active inquiry mode
   */
  function handlePrimaryModalAction() {
    if (!selectedRentalDate || !activeInquiry) return;

    if (activeInquiry.mode === 'check_availability') {
      performAvailabilityCheck();
    } else {
      confirmRentalDateAndOpenWhatsApp();
    }
  }

  /**
   * Check Live Availability via Backend API for Kediya & Choli
   * Sends product_code and selected date to /api/check-product
   */
  function performAvailabilityCheck() {
    if (!selectedRentalDate || !activeInquiry) return;

    const formattedDate = formatAsDDMMYYYY(selectedRentalDate);
    const productCode = activeInquiry.costumeCode;

    const resultContainer = document.getElementById('itAvailabilityResult');
    const actionBtn = document.getElementById('itContinueWaBtn');
    const btnText = document.getElementById('itBtnActionText');
    const waBtn = document.getElementById('itWhatsAppInquiryBtn');

    isChecking = true;
    if (actionBtn) actionBtn.disabled = true;
    if (btnText) btnText.textContent = 'Checking...';

    // Keep bottom action WhatsApp button strictly hidden (WhatsApp CTA is rendered cleanly inside the result card)
    if (waBtn) {
      waBtn.style.display = 'none';
      waBtn.disabled = true;
      waBtn.classList.remove('is-active-wa');
    }

    if (resultContainer) {
      resultContainer.style.display = 'block';
      resultContainer.innerHTML = `
        <div class="it-avail-card is-loading">
          <span class="it-spinner"></span>
          <span>Checking availability for ${productCode} on ${formattedDate}...</span>
        </div>
      `;
    }

    const apiUrl = `/api/check-product?product_code=${encodeURIComponent(productCode)}&date=${encodeURIComponent(formattedDate)}`;

    fetch(apiUrl)
      .then(function (res) {
        if (!res.ok) {
          throw new Error('Server returned ' + res.status);
        }
        return res.json();
      })
      .then(function (data) {
        isChecking = false;
        if (actionBtn) actionBtn.disabled = false;
        if (btnText) btnText.textContent = 'Check Availability';

        lastAvailabilityResult = data;

        if (!resultContainer) return;

        const effectiveCode = data.product_code || productCode;

        if (data.available === true) {
          resultContainer.innerHTML = `
            <div class="it-avail-card is-available">
              <div class="it-avail-status">✓ Available</div>
              <div class="it-avail-meta-rows">
                <div class="it-avail-row">
                  <span class="it-avail-row-label">Product Code:</span>
                  <span class="it-avail-row-val">${effectiveCode}</span>
                </div>
                <div class="it-avail-row">
                  <span class="it-avail-row-label">Date:</span>
                  <span class="it-avail-row-val">${formattedDate}</span>
                </div>
              </div>
              <div class="it-avail-success-hint">Costume is available! Tap "Inquire on WhatsApp" below to book.</div>
            </div>
          `;

          // Activate the modal's WhatsApp inquiry button
          if (waBtn) {
            waBtn.style.display = 'inline-flex';
            waBtn.disabled = false;
            waBtn.classList.add('is-active-wa');
          }
        } else {
          resultContainer.innerHTML = `
            <div class="it-avail-card is-unavailable">
              <div class="it-avail-status">✕ Not Available</div>
              <div class="it-avail-meta-rows">
                <div class="it-avail-row">
                  <span class="it-avail-row-label">Product Code:</span>
                  <span class="it-avail-row-val">${effectiveCode}</span>
                </div>
                <div class="it-avail-row">
                  <span class="it-avail-row-label">Date:</span>
                  <span class="it-avail-row-val">${formattedDate}</span>
                </div>
              </div>
              <div class="it-avail-reason">Please select another date.</div>
            </div>
          `;

          // Keep WhatsApp button disabled & neutral
          if (waBtn) {
            waBtn.style.display = 'inline-flex';
            waBtn.disabled = true;
            waBtn.classList.remove('is-active-wa');
          }
        }

        // Smooth scroll to reveal result if needed
        resultContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      })
      .catch(function (err) {
        isChecking = false;
        if (actionBtn) actionBtn.disabled = false;
        if (btnText) btnText.textContent = 'Check Availability';

        if (waBtn) {
          waBtn.style.display = 'inline-flex';
          waBtn.disabled = true;
          waBtn.classList.remove('is-active-wa');
        }

        if (resultContainer) {
          resultContainer.innerHTML = `
            <div class="it-avail-card is-unavailable">
              <div class="it-avail-status">✕ Check Failed</div>
              <div class="it-avail-reason">Unable to connect to availability service. Please try again.</div>
            </div>
          `;
        }
      });
  }

  /**
   * WhatsApp Trigger for Kediya & Choli
   * ONLY called when the costume has been confirmed AVAILABLE by backend
   */
  function triggerWhatsAppInquiry() {
    if (!lastAvailabilityResult || lastAvailabilityResult.available !== true) {
      alert('Please check availability for your required date first.');
      return;
    }
    if (!selectedRentalDate || !activeInquiry) return;

    const formattedDate = formatAsDDMMYYYY(selectedRentalDate);
    const productCode = lastAvailabilityResult.product_code || activeInquiry.costumeCode;
    const costumeImageUrl = resolvePublicImageUrl(
      activeInquiry.costumeImage || lastAvailabilityResult.image,
      activeInquiry.category
    );

    // Semantics: Product is confirmed available for this date -> inquire about the rental price
    const messageLines = [
      'Hello Image Traditional 👋',
      'I would like to inquire about this costume.',
      `Product Code: ${productCode}`,
      `Required Date: ${formattedDate}`,
      'Availability: Available',
      'This costume is available on this date, so what is the rental price?',
      `Costume Image: ${costumeImageUrl}`
    ];
    const message = messageLines.join('\n');

    const phone = activeInquiry.phone || '919428610384';
    const waUrl = `https://wa.me/${phone}?text=${encodeURIComponent(message)}`;

    // Open WhatsApp in a new tab/window
    window.open(waUrl, '_blank', 'noopener,noreferrer');

    // Instantly close modal and discard the selected date
    closeRentalDatePicker();
  }

  /**
   * WhatsApp Inquiry Generator (Fancy dress collection)
   * Builds the message, opens WhatsApp URL, and discards all temporary state
   */
  function confirmRentalDateAndOpenWhatsApp() {
    if (!selectedRentalDate || !activeInquiry) return;

    const formattedDate = formatAsDDMMYYYY(selectedRentalDate);

    // Build identifying costume name
    let costumeIdentifier = activeInquiry.costumeName;

    if (activeInquiry.category === 'Fancy' && activeInquiry.subcategory) {
      if (activeInquiry.costumeCode && activeInquiry.costumeCode !== activeInquiry.costumeName) {
        costumeIdentifier = `${activeInquiry.costumeName} (${activeInquiry.costumeCode}) (Fancy - ${activeInquiry.subcategory})`;
      } else {
        costumeIdentifier = `${activeInquiry.costumeName} (Fancy - ${activeInquiry.subcategory})`;
      }
    }

    // Required WhatsApp message format:
    // Hello Image Traditional, I would like to inquire about the availability of [Costume Name] for [DD-MM-YYYY]. Is it available for this date?
    const message = `Hello Image Traditional, I would like to inquire about the availability of ${costumeIdentifier} for ${formattedDate}. Is it available for this date?`;

    const phone = activeInquiry.phone || '919428610384';
    const waUrl = `https://wa.me/${phone}?text=${encodeURIComponent(message)}`;

    // Open WhatsApp in a new tab/window
    window.open(waUrl, '_blank', 'noopener,noreferrer');

    // Instantly close modal and discard the selected date
    closeRentalDatePicker();
  }

  /**
   * Universal WhatsApp button click handler inside modal
   * In whatsapp mode -> sends inquiry message
   * In check_availability mode -> sends verified availability inquiry
   */
  function handleWhatsAppBtnClick() {
    if (!activeInquiry || !selectedRentalDate) return;
    if (activeInquiry.mode === 'whatsapp') {
      confirmRentalDateAndOpenWhatsApp();
    } else {
      triggerWhatsAppInquiry();
    }
  }

  // Expose to window for inline onclick handlers and parent scripts
  window.openRentalDatePicker = openRentalDatePicker;
  window.closeRentalDatePicker = closeRentalDatePicker;
  window.handlePrimaryModalAction = handlePrimaryModalAction;
  window.triggerWhatsAppInquiry = triggerWhatsAppInquiry;
  window.confirmRentalDateAndOpenWhatsApp = confirmRentalDateAndOpenWhatsApp;
  window.handleWhatsAppBtnClick = handleWhatsAppBtnClick;
  window.navigateCalendarMonth = navigateCalendarMonth;

  // Keyboard and Backdrop Event Listeners
  document.addEventListener('DOMContentLoaded', function () {
    const modal = document.getElementById('itDatePickerModal');
    if (modal) {
      // Close on backdrop click (click outside card)
      modal.addEventListener('click', function (e) {
        if (e.target === modal) {
          closeRentalDatePicker();
        }
      });
    }

    // Handle Escape key
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        const dateModal = document.getElementById('itDatePickerModal');
        if (dateModal && dateModal.classList.contains('is-active')) {
          e.stopPropagation(); // Prevent closing underlying costume modal
          closeRentalDatePicker();
        }
      }
    }, true); // Capturing phase to handle before parent modals
  });
})();
