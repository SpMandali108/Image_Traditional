/**
 * PRODUCTION-GRADE CATALOG MANAGEMENT WORKSPACE (JS MODULE)
 * Handles State, Asynchronous REST APIs, Zoom Viewer, Tag Taxonomy & Keyboard Shortcuts
 */

(function () {
  'use strict';

  // Application State
  const state = {
    category: 'choli', // 'choli' or 'kediya'
    choliItems: [],
    kediyaItems: [],
    taxonomy: null,
    stats: null,
    selectedIndex: 0,
    activeTags: new Set(),
    activeNotes: '',
    unsavedChanges: false,
    searchQuery: '',
    filterMode: 'all', // 'all', 'tagged', 'untagged'
    bulkMode: false,
    selectedBulkNames: new Set(),
    zoomScale: 1,
    panX: 0,
    panY: 0,
    isDragging: false,
    dragStart: { x: 0, y: 0 },
    historyStack: [],
    autosaveTimer: null
  };

  // DOM Cache
  const dom = {};

  function initDOM() {
    dom.sidebar = document.getElementById('cwSidebar');
    dom.sidebarToggle = document.getElementById('cwSidebarToggle');
    dom.tabCholi = document.getElementById('cwTabCholi');
    dom.tabKediya = document.getElementById('cwTabKediya');
    dom.searchInput = document.getElementById('cwSearchInput');
    dom.filterAll = document.getElementById('cwFilterAll');
    dom.filterTagged = document.getElementById('cwFilterTagged');
    dom.filterUntagged = document.getElementById('cwFilterUntagged');
    dom.itemsList = document.getElementById('cwItemsList');
    
    dom.progressBar = document.getElementById('cwProgressBar');
    dom.progressText = document.getElementById('cwProgressText');
    dom.statusIndicator = document.getElementById('cwStatusIndicator');
    dom.statusText = document.getElementById('cwStatusText');

    dom.imageViewport = document.getElementById('cwImageViewport');
    dom.mainImg = document.getElementById('cwMainImg');
    dom.zoomInBtn = document.getElementById('cwZoomIn');
    dom.zoomOutBtn = document.getElementById('cwZoomOut');
    dom.zoomResetBtn = document.getElementById('cwZoomReset');
    dom.zoomFitBtn = document.getElementById('cwZoomFit');
    dom.fullscreenBtn = document.getElementById('cwFullscreen');
    dom.viewerTitle = document.getElementById('cwViewerTitle');

    dom.cardsGrid = document.getElementById('cwCardsGrid');
    dom.btnSaveNext = document.getElementById('cwBtnSaveNext');
    dom.btnPrev = document.getElementById('cwBtnPrev');
    dom.btnNext = document.getElementById('cwBtnNext');
    dom.btnBulkToggle = document.getElementById('cwBtnBulkToggle');
    dom.toastContainer = document.getElementById('cwToastContainer');
  }

  // Fetch Catalog & Taxonomy Data
  async function loadWorkspaceData() {
    // 1. Instant rendering from window.INITIAL_DATA if present
    if (window.INITIAL_DATA && Array.isArray(window.INITIAL_DATA.choli) && window.INITIAL_DATA.choli.length > 0) {
      state.choliItems = window.INITIAL_DATA.choli || [];
      state.kediyaItems = window.INITIAL_DATA.kediya || [];
      state.taxonomy = window.INITIAL_DATA.taxonomy || {};

      const choliTagged = state.choliItems.filter(x => x.tags && x.tags.length > 0).length;
      const kediyaTagged = state.kediyaItems.filter(x => x.tags && x.tags.length > 0).length;
      state.stats = {
        total_items: state.choliItems.length + state.kediyaItems.length,
        total_tagged: choliTagged + kediyaTagged
      };

      updateStatsUI();
      renderSidebarItems();
      renderTaxonomyCards();
      selectItem(0);
      showToast(`Workspace ready (${state.choliItems.length} Cholis & ${state.kediyaItems.length} Kediyas)`, 'success');
      return;
    }

    // 2. Fallback to API fetch
    try {
      showToast('Loading catalog data via API...', 'info');
      const response = await fetch('/api/catalog_workspace/data');
      const data = await response.json();

      if (data.status === 'success') {
        state.choliItems = data.choli || [];
        state.kediyaItems = data.kediya || [];
        state.taxonomy = data.taxonomy || {};
        state.stats = data.stats || {};

        updateStatsUI();
        renderSidebarItems();
        renderTaxonomyCards();
        selectItem(0);
        showToast('Catalog workspace ready', 'success');
      } else {
        showToast('Failed to load catalog data: ' + data.message, 'error');
      }
    } catch (err) {
      console.error(err);
      showToast('Connection error while fetching data', 'error');
    }
  }

  // Helper: Get Current Items Array
  function getActiveItems() {
    return state.category === 'choli' ? state.choliItems : state.kediyaItems;
  }

  // Update Header Progress Bar
  function updateStatsUI() {
    if (!state.stats) return;
    const total = state.stats.total_items || 1;
    const tagged = state.stats.total_tagged || 0;
    const percent = Math.round((tagged / total) * 100);

    if (dom.progressBar) dom.progressBar.style.width = percent + '%';
    if (dom.progressText) dom.progressText.textContent = `${tagged} / ${total} Tagged (${percent}%)`;
  }

  // Render Left Sidebar List
  function renderSidebarItems() {
    const items = getActiveItems();
    dom.itemsList.innerHTML = '';

    const query = state.searchQuery.trim().toLowerCase();

    let renderedCount = 0;
    items.forEach((item, index) => {
      // Search matching by code, tags, or notes
      const codeMatch = item.name.toLowerCase().includes(query);
      const tagMatch = (item.tags || []).some(t => t.toLowerCase().includes(query));
      const noteMatch = (item.notes || '').toLowerCase().includes(query);
      const passesSearch = query === '' || codeMatch || tagMatch || noteMatch;

      const isTagged = item.tags && item.tags.length > 0;
      
      let passFilter = true;
      if (state.filterMode === 'tagged' && !isTagged) passFilter = false;
      if (state.filterMode === 'untagged' && isTagged) passFilter = false;

      if (!passesSearch || !passFilter) return;

      renderedCount++;

      const card = document.createElement('div');
      card.className = `cw-item-card ${index === state.selectedIndex ? 'selected' : ''}`;
      card.dataset.index = index;

      const folder = state.category === 'choli' ? 'Choli' : 'Kediya';
      const folderJpg = state.category === 'choli' ? 'CholiJpg' : 'KediyaJpg';
      const imgPath = `/static/${folder}/${item.image}`;
      const fallbackPath = `/static/${folderJpg}/${item.name}.jpg`;

      const tagCount = item.tags ? item.tags.length : 0;
      const badgeClass = isTagged ? 'tagged' : 'untagged';
      const badgeText = isTagged ? `${tagCount} Tags` : 'Untagged';

      const isBulkChecked = state.selectedBulkNames.has(item.name);

      card.innerHTML = `
        <input type="checkbox" class="cw-item-checkbox" ${isBulkChecked ? 'checked' : ''}>
        <img class="cw-item-thumb" src="${imgPath}" alt="${item.name}" loading="lazy" onerror="this.onerror=null; this.src='${fallbackPath}';">
        <div class="cw-item-info">
          <div class="cw-item-code">${item.name}</div>
          <div class="cw-item-tag-count">${item.notes ? '📝 Has Notes' : (isTagged ? item.tags.slice(0, 2).join(', ') : 'No tags')}</div>
        </div>
        <span class="cw-item-badge ${badgeClass}">${badgeText}</span>
      `;

      card.addEventListener('click', (e) => {
        if (e.target.classList.contains('cw-item-checkbox')) {
          if (e.target.checked) state.selectedBulkNames.add(item.name);
          else state.selectedBulkNames.delete(item.name);
          return;
        }
        if (state.unsavedChanges) saveCurrentItem(false);
        selectItem(index);
      });

      dom.itemsList.appendChild(card);
    });

    // Empty state handling
    if (renderedCount === 0) {
      const emptyDiv = document.createElement('div');
      emptyDiv.style.cssText = 'padding:24px 16px; text-align:center; color:var(--cw-text-muted); font-size:0.85rem; display:flex; flex-direction:column; gap:12px; align-items:center;';
      emptyDiv.innerHTML = `
        <div>🔍 No products match "${state.searchQuery || state.filterMode}" filter.</div>
        <button id="cwResetSearchBtn" class="cw-btn-secondary" style="padding:6px 14px; font-size:0.78rem;">Reset Search & Filters</button>
      `;
      dom.itemsList.appendChild(emptyDiv);

      const resetBtn = emptyDiv.querySelector('#cwResetSearchBtn');
      if (resetBtn) {
        resetBtn.onclick = () => {
          state.searchQuery = '';
          state.filterMode = 'all';
          if (dom.searchInput) dom.searchInput.value = '';
          setActiveFilterPill(dom.filterAll);
          renderSidebarItems();
        };
      }
    }
  }

  // Select Item & Update Workspace
  function selectItem(index) {
    const items = getActiveItems();
    if (!items || items.length === 0) return;
    if (index < 0) index = 0;
    if (index >= items.length) index = items.length - 1;

    state.selectedIndex = index;
    const item = items[index];
    if (!item) return;

    state.activeTags = new Set(item.tags || []);
    state.activeNotes = item.notes || '';
    state.unsavedChanges = false;
    updateStatusIndicator('Saved', 'saved');

    // Update Image Viewport with fallback
    const folder = state.category === 'choli' ? 'Choli' : 'Kediya';
    const folderJpg = state.category === 'choli' ? 'CholiJpg' : 'KediyaJpg';
    const imgPath = `/static/${folder}/${item.image}`;
    const fallbackPath = `/static/${folderJpg}/${item.name}.jpg`;

    dom.mainImg.onerror = function() {
      this.onerror = function() {
        this.onerror = null;
        this.src = '/static/Home_Img/favicon.png';
      };
      this.src = fallbackPath;
    };
    dom.mainImg.src = imgPath;
    resetZoom();

    if (dom.viewerTitle) {
      dom.viewerTitle.textContent = `${state.category.toUpperCase()} — ${item.name}`;
    }

    // Refresh Sidebar Highlights
    const cards = dom.itemsList.querySelectorAll('.cw-item-card');
    cards.forEach(c => {
      if (parseInt(c.dataset.index) === index) c.classList.add('selected');
      else c.classList.remove('selected');
    });

    // Sync Tag Chips UI
    syncChipsUI();
  }

  // Sync Chip Active States & Notes
  function syncChipsUI() {
    const chips = dom.cardsGrid.querySelectorAll('.cw-chip[data-tag]');
    chips.forEach(chip => {
      const tag = chip.dataset.tag;
      if (state.activeTags.has(tag)) chip.classList.add('active');
      else chip.classList.remove('active');
    });

    const notesTxt = document.getElementById('cwNotesTextarea');
    if (notesTxt) notesTxt.value = state.activeNotes;

    renderActiveTagsSummary();
  }

  // Render Top Active Tags Summary Card
  function renderActiveTagsSummary() {
    let summaryCard = document.getElementById('cwSummaryCard');
    if (!summaryCard) {
      summaryCard = document.createElement('div');
      summaryCard.id = 'cwSummaryCard';
      summaryCard.className = 'cw-summary-card';
      dom.cardsGrid.prepend(summaryCard);
    }

    const activeList = Array.from(state.activeTags);
    if (activeList.length === 0) {
      summaryCard.innerHTML = `
        <div class="cw-summary-header">
          <span class="cw-summary-title">🏷️ Active Tags (0)</span>
        </div>
        <div style="font-size:0.8rem; color:var(--cw-text-muted);">No tags applied yet. Click any button below to add tags.</div>
      `;
      return;
    }

    summaryCard.innerHTML = `
      <div class="cw-summary-header">
        <span class="cw-summary-title">🏷️ Active Tags (${activeList.length})</span>
        <button class="cw-btn-clear-all" id="cwBtnClearAll">Clear All Tags</button>
      </div>
      <div class="cw-chips-grid" id="cwActiveChipsGrid"></div>
    `;

    document.getElementById('cwBtnClearAll').onclick = () => {
      recordHistory();
      state.activeTags.clear();
      markUnsaved();
      syncChipsUI();
      triggerAutosave();
      showToast('Cleared all tags from item', 'info');
    };

    const grid = summaryCard.querySelector('#cwActiveChipsGrid');
    activeList.forEach(tag => {
      const chip = document.createElement('div');
      chip.className = 'cw-active-tag-chip';
      chip.innerHTML = `
        <span>${tag}</span>
        <span class="cw-tag-remove-x" title="Remove tag">✕</span>
      `;
      chip.querySelector('.cw-tag-remove-x').onclick = (e) => {
        e.stopPropagation();
        toggleTag(tag);
      };
      grid.appendChild(chip);
    });
  }

  // Toggle Single Tag
  function toggleTag(tag) {
    recordHistory();
    if (state.activeTags.has(tag)) {
      state.activeTags.delete(tag);
    } else {
      state.activeTags.add(tag);
    }
    markUnsaved();
    syncChipsUI();
    triggerAutosave();
  }

  // Apply Preset Macro
  function applyPreset(presetTags) {
    recordHistory();
    presetTags.forEach(t => state.activeTags.add(t));
    markUnsaved();
    syncChipsUI();
    showToast('Applied preset tags', 'success');
    triggerAutosave();
  }

  // Permanently Delete Preset Macro
  async function deletePreset(presetId, label) {
    if (!confirm(`Are you sure you want to delete the preset '${label}'?`)) return;

    try {
      showToast(`Deleting preset '${label}'...`, 'info');
      const response = await fetch('/api/catalog_workspace/delete_preset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preset_id: presetId, label: label })
      });
      const data = await response.json();

      if (data.status === 'success') {
        state.taxonomy = data.taxonomy || state.taxonomy;
        renderTaxonomyCards();
        showToast(data.message, 'success');
      } else {
        showToast(data.message, 'error');
      }
    } catch (err) {
      console.error(err);
      showToast('Error deleting preset', 'error');
    }
  }

  // Permanently Delete Taxonomy Option
  async function deleteTaxonomyOption(groupId, tagLabel) {
    if (!confirm(`Are you sure you want to delete the tag option '${tagLabel}' from the taxonomy pool?`)) return;

    try {
      showToast(`Deleting option '${tagLabel}'...`, 'info');
      const response = await fetch('/api/catalog_workspace/delete_tag', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ group_id: groupId, tag_label: tagLabel })
      });
      const data = await response.json();

      if (data.status === 'success') {
        state.taxonomy = data.taxonomy || state.taxonomy;
        if (state.activeTags.has(tagLabel)) {
          state.activeTags.delete(tagLabel);
        }
        renderTaxonomyCards();
        syncChipsUI();
        showToast(data.message, 'success');
      } else {
        showToast(data.message, 'error');
      }
    } catch (err) {
      console.error(err);
      showToast('Error deleting tag option', 'error');
    }
  }

  // Mark Unsaved & Trigger Autosave
  function markUnsaved() {
    state.unsavedChanges = true;
    updateStatusIndicator('Unsaved Changes', 'unsaved');
  }

  function triggerAutosave() {
    if (state.autosaveTimer) clearTimeout(state.autosaveTimer);
    state.autosaveTimer = setTimeout(() => {
      saveCurrentItem(true);
    }, 1000);
  }

  // Status Indicator
  function updateStatusIndicator(text, type) {
    if (!dom.statusIndicator) return;
    dom.statusIndicator.className = `cw-status-indicator ${type}`;
    if (dom.statusText) dom.statusText.textContent = text;
  }

  // Record History for Undo
  function recordHistory() {
    state.historyStack.push({
      tags: new Set(state.activeTags),
      notes: state.activeNotes
    });
    if (state.historyStack.length > 20) state.historyStack.shift();
  }

  function undoLastChange() {
    if (state.historyStack.length === 0) return;
    const prev = state.historyStack.pop();
    state.activeTags = prev.tags;
    state.activeNotes = prev.notes;
    markUnsaved();
    syncChipsUI();
    showToast('Undid last change', 'info');
  }

  // Save Item API Call
  async function saveCurrentItem(silent = false) {
    const items = getActiveItems();
    if (state.selectedIndex < 0 || state.selectedIndex >= items.length) return;

    const item = items[state.selectedIndex];
    updateStatusIndicator('Saving...', 'saving');

    const notesTxt = document.getElementById('cwNotesTextarea');
    if (notesTxt) state.activeNotes = notesTxt.value;

    const payload = {
      category: state.category,
      name: item.name,
      tags: Array.from(state.activeTags),
      notes: state.activeNotes
    };

    try {
      const response = await fetch('/api/catalog_workspace/save_item', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await response.json();

      if (data.status === 'success') {
        item.tags = payload.tags;
        item.notes = payload.notes;
        state.unsavedChanges = false;
        state.stats = data.stats || state.stats;

        updateStatsUI();
        renderSidebarItems();
        updateStatusIndicator('Saved', 'saved');
        if (!silent) showToast(`Saved tags for ${item.name}`, 'success');
      } else {
        updateStatusIndicator('Error Saving', 'unsaved');
        showToast('Error saving: ' + data.message, 'error');
      }
    } catch (err) {
      console.error(err);
      updateStatusIndicator('Network Error', 'unsaved');
      showToast('Network error on save', 'error');
    }
  }

  // Category Management REST API Handlers
  async function addCategory(title) {
    try {
      showToast(`Adding category '${title}'...`, 'info');
      const response = await fetch('/api/catalog_workspace/add_category', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: title })
      });
      const data = await response.json();
      if (data.status === 'success') {
        state.taxonomy = data.taxonomy || state.taxonomy;
        renderTaxonomyCards();
        showToast(data.message, 'success');
      } else {
        showToast(data.message, 'error');
      }
    } catch (err) {
      console.error(err);
      showToast('Error adding category', 'error');
    }
  }

  async function editCategory(groupId, currentTitle) {
    const newTitle = prompt('Enter new Category Title:', currentTitle);
    if (!newTitle || newTitle.trim() === '' || newTitle === currentTitle) return;

    try {
      showToast(`Updating category title...`, 'info');
      const response = await fetch('/api/catalog_workspace/edit_category', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ group_id: groupId, new_title: newTitle.trim() })
      });
      const data = await response.json();
      if (data.status === 'success') {
        state.taxonomy = data.taxonomy || state.taxonomy;
        renderTaxonomyCards();
        showToast(data.message, 'success');
      } else {
        showToast(data.message, 'error');
      }
    } catch (err) {
      console.error(err);
      showToast('Error editing category', 'error');
    }
  }

  async function deleteCategory(groupId, currentTitle) {
    if (!confirm(`Are you sure you want to delete the category '${currentTitle}' and all its tags?`)) return;

    try {
      showToast(`Deleting category '${currentTitle}'...`, 'info');
      const response = await fetch('/api/catalog_workspace/delete_category', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ group_id: groupId })
      });
      const data = await response.json();
      if (data.status === 'success') {
        state.taxonomy = data.taxonomy || state.taxonomy;
        renderTaxonomyCards();
        showToast(data.message, 'success');
      } else {
        showToast(data.message, 'error');
      }
    } catch (err) {
      console.error(err);
      showToast('Error deleting category', 'error');
    }
  }

  async function editTagOption(groupId, oldLabel) {
    const newLabel = prompt(`Rename tag '${oldLabel}' to:`, oldLabel);
    if (!newLabel || newLabel.trim() === '' || newLabel === oldLabel) return;

    try {
      showToast(`Renaming tag '${oldLabel}' to '${newLabel.trim()}'...`, 'info');
      const response = await fetch('/api/catalog_workspace/edit_tag', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ group_id: groupId, old_label: oldLabel, new_label: newLabel.trim() })
      });
      const data = await response.json();
      if (data.status === 'success') {
        state.taxonomy = data.taxonomy || state.taxonomy;
        if (state.activeTags.has(oldLabel)) {
          state.activeTags.delete(oldLabel);
          state.activeTags.add(newLabel.trim());
        }
        renderTaxonomyCards();
        syncChipsUI();
        showToast(data.message, 'success');
      } else {
        showToast(data.message, 'error');
      }
    } catch (err) {
      console.error(err);
      showToast('Error editing tag option', 'error');
    }
  }

  // Render Dynamic Taxonomy Cards
  function renderTaxonomyCards() {
    if (!state.taxonomy) return;
    dom.cardsGrid.innerHTML = '';

    // Render Summary Card
    renderActiveTagsSummary();

    // Add New Category Header Action
    const addCatBar = document.createElement('div');
    addCatBar.style.cssText = 'display:flex; justify-content:space-between; align-items:center; background:var(--cw-bg-surface); padding:10px 18px; border-radius:var(--cw-radius-md); border:1px solid var(--cw-border-subtle);';
    addCatBar.innerHTML = `
      <span style="font-size:0.88rem; font-weight:700; color:var(--cw-text-primary);">📁 Category Groups</span>
      <button id="cwBtnAddCategory" class="cw-btn-add" style="padding:6px 14px;">+ Add New Category</button>
    `;
    dom.cardsGrid.appendChild(addCatBar);

    addCatBar.querySelector('#cwBtnAddCategory').onclick = () => {
      const title = prompt('Enter New Category Group Title (e.g. Fabric Material, Sleeve Style):');
      if (title && title.trim()) {
        addCategory(title.trim());
      }
    };

    // Render Taxonomy Groups
    const groups = state.taxonomy.groups || [];
    groups.forEach(group => {
      const card = document.createElement('div');
      card.className = 'cw-card';
      card.dataset.groupId = group.id;

      card.innerHTML = `
        <div class="cw-card-header">
          <span class="cw-card-title">${group.title}</span>
          <div style="display:flex; align-items:center; gap:8px;">
            <button class="cw-icon-btn cw-btn-edit-cat" style="width:26px; height:26px; font-size:0.75rem;" title="Rename Category">✏️</button>
            <button class="cw-icon-btn cw-btn-del-cat" style="width:26px; height:26px; font-size:0.75rem; color:var(--cw-accent-red);" title="Delete Category">🗑️</button>
            <span class="cw-card-arrow">▼</span>
          </div>
        </div>
        <div class="cw-card-body">
          <div class="cw-chips-grid" id="group_chips_${group.id}"></div>
          <div class="cw-add-tag-bar">
            <input type="text" class="cw-add-input" id="add_input_${group.id}" placeholder="+ Add custom tag option...">
            <button class="cw-btn-add" id="add_btn_${group.id}">Add</button>
          </div>
        </div>
      `;

      // Header actions
      const header = card.querySelector('.cw-card-header');
      header.onclick = (e) => {
        if (e.target.classList.contains('cw-btn-edit-cat')) {
          e.stopPropagation();
          editCategory(group.id, group.title);
          return;
        }
        if (e.target.classList.contains('cw-btn-del-cat')) {
          e.stopPropagation();
          deleteCategory(group.id, group.title);
          return;
        }
        card.classList.toggle('collapsed');
      };

      // Populate Chips
      const chipsContainer = card.querySelector(`#group_chips_${group.id}`);
      (group.options || []).forEach(opt => {
        const chip = document.createElement('div');
        chip.className = 'cw-chip';
        chip.dataset.tag = opt.label;
        chip.innerHTML = `
          <span>${opt.icon ? opt.icon + ' ' : ''}${opt.label}</span>
          <span class="cw-option-edit-btn" title="Rename tag option" style="font-size:0.72rem; margin-left:4px; opacity:0.6; cursor:pointer;">✏️</span>
          <span class="cw-option-delete-btn" title="Delete option from pool">✕</span>
        `;
        chip.onclick = (e) => {
          if (e.target.classList.contains('cw-option-edit-btn')) {
            e.stopPropagation();
            editTagOption(group.id, opt.label);
            return;
          }
          if (e.target.classList.contains('cw-option-delete-btn')) {
            e.stopPropagation();
            deleteTaxonomyOption(group.id, opt.label);
            return;
          }
          toggleTag(opt.label);
        };
        chipsContainer.appendChild(chip);
      });

      // Add Custom Tag Listener
      const addInput = card.querySelector(`#add_input_${group.id}`);
      const addBtn = card.querySelector(`#add_btn_${group.id}`);

      const handleAdd = () => {
        const val = addInput.value.strip ? addInput.value.strip() : addInput.value.trim();
        if (val) {
          createCustomTag(group.id, val);
          addInput.value = '';
        }
      };

      addBtn.onclick = handleAdd;
      addInput.onkeydown = (e) => { if (e.key === 'Enter') handleAdd(); };

      dom.cardsGrid.appendChild(card);
    });

    // Append Notes Card
    const notesCard = document.createElement('div');
    notesCard.className = 'cw-card';
    notesCard.innerHTML = `
      <div class="cw-card-header">
        <span class="cw-card-title">📝 Item Fitting & Alteration Notes</span>
        <span class="cw-card-arrow">▼</span>
      </div>
      <div class="cw-card-body">
        <textarea id="cwNotesTextarea" class="cw-notes-textarea" placeholder="Add custom alteration notes, damage history, or tailor instructions..."></textarea>
      </div>
    `;
    const txt = notesCard.querySelector('#cwNotesTextarea');
    txt.oninput = () => {
      state.activeNotes = txt.value;
      markUnsaved();
      triggerAutosave();
    };
    dom.cardsGrid.appendChild(notesCard);
  }

  // Create Custom Tag API Call
  async function createCustomTag(groupId, tagName) {
    try {
      showToast(`Creating custom tag '${tagName}'...`, 'info');
      const response = await fetch('/api/catalog_workspace/create_tag', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ group_id: groupId, tag_name: tagName })
      });
      const data = await response.json();

      if (data.status === 'success' || data.status === 'warning') {
        state.taxonomy = data.taxonomy || state.taxonomy;
        renderTaxonomyCards();
        toggleTag(tagName);
        showToast(data.message, 'success');
      } else {
        showToast(data.message, 'error');
      }
    } catch (err) {
      console.error(err);
      showToast('Error creating tag', 'error');
    }
  }

  // Zoom & Pan Viewer Controls
  function setZoom(scale) {
    state.zoomScale = Math.max(1, Math.min(scale, 5));
    if (state.zoomScale === 1) {
      state.panX = 0;
      state.panY = 0;
    }
    applyTransform();
  }

  function resetZoom() {
    state.zoomScale = 1;
    state.panX = 0;
    state.panY = 0;
    applyTransform();
  }

  function applyTransform() {
    dom.mainImg.style.transform = `translate(${state.panX}px, ${state.panY}px) scale(${state.zoomScale})`;
  }

  function initViewerEvents() {
    dom.zoomInBtn.onclick = () => setZoom(state.zoomScale + 0.5);
    dom.zoomOutBtn.onclick = () => setZoom(state.zoomScale - 0.5);
    dom.zoomResetBtn.onclick = () => resetZoom();
    dom.zoomFitBtn.onclick = () => resetZoom();

    dom.fullscreenBtn.onclick = () => {
      if (!document.fullscreenElement) {
        dom.imageViewport.requestFullscreen().catch(err => console.error(err));
      } else {
        document.exitFullscreen();
      }
    };

    dom.imageViewport.onwheel = (e) => {
      e.preventDefault();
      const delta = e.deltaY < 0 ? 0.2 : -0.2;
      setZoom(state.zoomScale + delta);
    };

    // Pan Dragging
    dom.imageViewport.onmousedown = (e) => {
      if (state.zoomScale > 1) {
        state.isDragging = true;
        state.dragStart = { x: e.clientX - state.panX, y: e.clientY - state.panY };
      }
    };

    window.onmousemove = (e) => {
      if (state.isDragging) {
        state.panX = e.clientX - state.dragStart.x;
        state.panY = e.clientY - state.dragStart.y;
        applyTransform();
      }
    };

    window.onmouseup = () => { state.isDragging = false; };
  }

  // Keyboard Shortcuts Listener
  function initKeyboardShortcuts() {
    window.addEventListener('keydown', (e) => {
      if (['INPUT', 'TEXTAREA'].includes(e.target.tagName)) return;

      if (e.key === 'Enter') {
        e.preventDefault();
        saveCurrentItem(false);
        selectItem(state.selectedIndex + 1);
      } else if (e.key === 'j' || e.key === 'J' || e.key === 'ArrowDown') {
        e.preventDefault();
        selectItem(state.selectedIndex + 1);
      } else if (e.key === 'k' || e.key === 'K' || e.key === 'ArrowUp') {
        e.preventDefault();
        selectItem(state.selectedIndex - 1);
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
        e.preventDefault();
        saveCurrentItem(false);
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
        e.preventDefault();
        undoLastChange();
      } else if (e.key === 'Escape') {
        resetZoom();
      }
    });
  }

  // Toast System
  function showToast(message, type = 'info') {
    if (!dom.toastContainer) return;
    const toast = document.createElement('div');
    toast.className = `cw-toast ${type}`;
    const icon = type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️';
    toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
    dom.toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(-10px)';
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  // Bind Header & Sidebar Controls
  function bindControls() {
    if (dom.sidebarToggle) {
      dom.sidebarToggle.onclick = () => dom.sidebar.classList.toggle('collapsed');
    }

    dom.tabCholi.onclick = () => {
      if (state.category === 'choli') return;
      state.category = 'choli';
      dom.tabCholi.classList.add('active');
      dom.tabKediya.classList.remove('active');
      renderSidebarItems();
      selectItem(0);
    };

    dom.tabKediya.onclick = () => {
      if (state.category === 'kediya') return;
      state.category = 'kediya';
      dom.tabKediya.classList.add('active');
      dom.tabCholi.classList.remove('active');
      renderSidebarItems();
      selectItem(0);
    };

    dom.searchInput.oninput = (e) => {
      state.searchQuery = e.target.value;
      renderSidebarItems();
    };

    dom.filterAll.onclick = () => {
      state.filterMode = 'all';
      setActiveFilterPill(dom.filterAll);
      renderSidebarItems();
    };

    dom.filterTagged.onclick = () => {
      state.filterMode = 'tagged';
      setActiveFilterPill(dom.filterTagged);
      renderSidebarItems();
    };

    dom.filterUntagged.onclick = () => {
      state.filterMode = 'untagged';
      setActiveFilterPill(dom.filterUntagged);
      renderSidebarItems();
    };

    dom.btnSaveNext.onclick = () => {
      saveCurrentItem(false);
      selectItem(state.selectedIndex + 1);
    };

    dom.btnPrev.onclick = () => selectItem(state.selectedIndex - 1);
    dom.btnNext.onclick = () => selectItem(state.selectedIndex + 1);
  }

  function setActiveFilterPill(activePill) {
    [dom.filterAll, dom.filterTagged, dom.filterUntagged].forEach(p => p.classList.remove('active'));
    activePill.classList.add('active');
  }

  // Boot Application
  document.addEventListener('DOMContentLoaded', () => {
    document.body.classList.add('cw-active-body');
    initDOM();
    initViewerEvents();
    initKeyboardShortcuts();
    bindControls();
    loadWorkspaceData();
  });
})();
