import os
import json
import re

def generate_offline_catalogue_html():
    # 1. Load Kediya
    with open('kediya.json', 'r', encoding='utf-8') as f:
        kediya_raw = json.load(f)
    kediya_items = []
    for item in kediya_raw:
        kediya_items.append({
            'code': item['name'],
            'name': f"Traditional Kediya {item['name']}",
            'cat': 'kediya',
            'img': f"/static/Kediya/{item['image']}",
            'fallback_img': f"/static/KediyaJpg/{item['name']}.jpg",
            'desc': f"Hand-crafted traditional festive Kediya outfit {item['name']} featuring authentic mirror work and vibrant Gujarati embroidery."
        })

    # 2. Load Choli
    with open('choli.json', 'r', encoding='utf-8') as f:
        choli_raw = json.load(f)
    choli_items = []
    for item in choli_raw:
        choli_items.append({
            'code': item['name'],
            'name': f"Chaniya Choli {item['name']}",
            'cat': 'choli',
            'img': f"/static/Choli/{item['image']}",
            'fallback_img': f"/static/CholiJpg/{item['name']}.jpg",
            'desc': f"Artisan crafted Chaniya Choli {item['name']} with festive flare, intricate hand-embroidery, and traditional patterns."
        })

    # 3. Load Fancy
    icon_map = {
        'Bhagwan': 'bhagwan.png', 'Mataji': 'mataji.png', 'Profession': 'Proffesion.png',
        'Freedom Fighter': 'Freedom Fighter.png', 'Regional': 'Regional.png',
        'Wild Animals': 'Wild Animal.png', 'Domestic Animals': 'Domestic Animal.png',
        'Water Animals': 'Water Animal.png', 'Insects': 'Insect.png', 'Birds': 'Bird.png',
        'Fruits': 'fruit.png', 'Vegetables': 'vegetable.png', 'Halloween': 'Halloween.png',
        'Cartoon': 'Cartoon.png', 'Superhero': 'Superhero.png', 'International': 'International.png',
        'Flexi': 'Flex.png', 'Nature': 'Nature.png', 'Tiranga': 'Tiranga.png', 'Others': 'Other.png'
    }
    desc_path = os.path.join('website', 'static', 'fancy_descriptions.json')
    descriptions = {}
    if os.path.exists(desc_path):
        with open(desc_path, 'r', encoding='utf-8') as df:
            descriptions = json.load(df)

    base_fancy_dir = os.path.join('website', 'static', 'Products', 'Fancy')
    fancy_items = []
    categories_list = []
    for subfolder, icon in icon_map.items():
        folder_path = os.path.join(base_fancy_dir, subfolder)
        cat_count = 0
        if os.path.exists(folder_path):
            for f in sorted(os.listdir(folder_path)):
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    stem = os.path.splitext(f)[0].replace('_', ' ').replace('-', ' ')
                    clean = re.sub(r'[^a-zA-Z ]', '', stem).strip().title()
                    desc = descriptions.get(f'{subfolder}/{f}', f"High quality stage costume representing {clean} in category {subfolder}.")
                    fancy_items.append({
                        'code': f"{subfolder} - {clean}",
                        'name': clean,
                        'cat': 'fancy',
                        'subcat': subfolder,
                        'img': f"/static/Products/Fancy/{subfolder}/{f}",
                        'fallback_img': f"/static/Icons/{icon}",
                        'desc': desc
                    })
                    cat_count += 1
        categories_list.append({'name': subfolder, 'icon': icon, 'count': cat_count})

    catalogue_data = {
        'kediya': kediya_items,
        'choli': choli_items,
        'fancy': fancy_items,
        'fancy_categories': categories_list
    }

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0">
  <title>Offline Catalogue | Image Traditional</title>
  <link rel="icon" href="/static/Home_Img/favicon.png">
  <meta name="theme-color" content="#050D1F">
  <style>
    :root {{
      --bg: #050D1F;
      --card-bg: #0F1F3D;
      --surface: #14244B;
      --gold: #D4AF37;
      --gold-light: #F5D580;
      --gold-dark: #B8961E;
      --text: #F8FAFC;
      --text-muted: #94A3B8;
      --border: rgba(212, 175, 55, 0.28);
      --border-subtle: rgba(255, 255, 255, 0.08);
    }}
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      color: var(--text);
      font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }}
    /* Top Offline Banner */
    .offline-banner {{
      background: linear-gradient(90deg, #1e1b4b, #0f172a, #1e1b4b);
      border-bottom: 1px solid var(--border);
      padding: 10px 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .badge-offline {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: rgba(212, 175, 55, 0.15);
      border: 1px solid var(--gold);
      color: var(--gold-light);
      padding: 4px 12px;
      border-radius: 20px;
      font-size: 0.8rem;
      font-weight: 700;
      letter-spacing: 0.5px;
    }}
    .banner-right {{
      display: flex;
      gap: 8px;
      align-items: center;
    }}
    .btn-action {{
      background: rgba(255,255,255,0.08);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 6px 14px;
      border-radius: 8px;
      font-size: 0.85rem;
      cursor: pointer;
      text-decoration: none;
      transition: all 0.2s;
    }}
    .btn-action:hover {{ background: rgba(212,175,55,0.2); border-color: var(--gold); color: var(--gold-light); }}
    .btn-call {{
      background: var(--gold);
      color: var(--bg);
      font-weight: 700;
      border: none;
    }}

    /* Main Container */
    .container {{
      max-width: 1200px;
      width: 100%;
      margin: 0 auto;
      padding: 16px;
      flex: 1;
    }}

    /* Header */
    .app-header {{
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 16px;
    }}
    .brand-icon {{
      width: 44px;
      height: 44px;
      border-radius: 50%;
      border: 2px solid var(--gold);
    }}
    .app-title {{
      font-size: 1.4rem;
      font-weight: 800;
      color: var(--gold-light);
    }}
    .app-subtitle {{
      font-size: 0.85rem;
      color: var(--text-muted);
    }}

    /* Tabs */
    .tabs-bar {{
      display: flex;
      gap: 8px;
      background: var(--card-bg);
      padding: 6px;
      border-radius: 12px;
      border: 1px solid var(--border-subtle);
      margin-bottom: 16px;
      overflow-x: auto;
    }}
    .tab-btn {{
      flex: 1;
      min-width: 120px;
      padding: 10px 14px;
      border-radius: 8px;
      border: none;
      background: transparent;
      color: var(--text-muted);
      font-size: 0.92rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
      white-space: nowrap;
      text-align: center;
    }}
    .tab-btn.active {{
      background: var(--gold);
      color: var(--bg);
      box-shadow: 0 2px 10px rgba(212,175,55,0.3);
    }}

    /* Search & Filter Bar */
    .filter-section {{
      background: var(--card-bg);
      border: 1px solid var(--border-subtle);
      border-radius: 12px;
      padding: 12px;
      margin-bottom: 18px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}
    .search-row {{
      display: flex;
      gap: 10px;
      align-items: center;
    }}
    .search-input {{
      flex: 1;
      background: var(--surface);
      border: 1px solid var(--border-subtle);
      padding: 10px 14px;
      border-radius: 8px;
      color: var(--text);
      font-size: 0.95rem;
      outline: none;
    }}
    .search-input:focus {{ border-color: var(--gold); }}
    .pills-row {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .pill-btn {{
      background: rgba(255,255,255,0.05);
      border: 1px solid var(--border-subtle);
      color: var(--text-muted);
      padding: 5px 12px;
      border-radius: 16px;
      font-size: 0.8rem;
      cursor: pointer;
      transition: all 0.2s;
    }}
    .pill-btn.active {{
      background: rgba(212,175,55,0.2);
      border-color: var(--gold);
      color: var(--gold-light);
      font-weight: 600;
    }}

    /* Status Text */
    .results-count {{
      font-size: 0.85rem;
      color: var(--text-muted);
      margin-bottom: 14px;
    }}

    /* Product Grid */
    .products-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
      gap: 14px;
    }}
    @media (min-width: 600px) {{
      .products-grid {{
        grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
        gap: 18px;
      }}
    }}

    /* Card */
    .product-card {{
      background: var(--card-bg);
      border: 1px solid var(--border-subtle);
      border-radius: 12px;
      overflow: hidden;
      cursor: pointer;
      transition: transform 0.2s, border-color 0.2s, box-shadow 0.2s;
      display: flex;
      flex-direction: column;
    }}
    .product-card:hover {{
      transform: translateY(-3px);
      border-color: var(--gold);
      box-shadow: 0 8px 24px rgba(0,0,0,0.5);
    }}
    .img-wrap {{
      width: 100%;
      aspect-ratio: 1 / 1;
      background: #020612;
      position: relative;
      overflow: hidden;
    }}
    .img-wrap img {{
      width: 100%;
      height: 100%;
      object-fit: cover;
      transition: transform 0.3s ease;
    }}
    .product-card:hover .img-wrap img {{
      transform: scale(1.04);
    }}
    .card-body {{
      padding: 10px 12px;
      display: flex;
      flex-direction: column;
      flex: 1;
    }}
    .card-code {{
      font-size: 0.95rem;
      font-weight: 700;
      color: var(--gold-light);
      margin-bottom: 2px;
    }}
    .card-tag {{
      font-size: 0.72rem;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 6px;
    }}
    .card-desc {{
      font-size: 0.78rem;
      color: #94A3B8;
      line-height: 1.35;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
      flex: 1;
      margin-bottom: 8px;
    }}
    .btn-view {{
      background: rgba(212,175,55,0.1);
      border: 1px solid var(--border);
      color: var(--gold-light);
      padding: 6px;
      border-radius: 6px;
      font-size: 0.8rem;
      font-weight: 600;
      text-align: center;
    }}

    /* Lightbox Modal */
    .modal-backdrop {{
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0,0,0,0.85);
      backdrop-filter: blur(8px);
      display: none;
      align-items: center;
      justify-content: center;
      padding: 16px;
      z-index: 1000;
    }}
    .modal-card {{
      background: var(--card-bg);
      border: 1px solid var(--gold);
      border-radius: 16px;
      max-width: 520px;
      width: 100%;
      max-height: 90vh;
      overflow-y: auto;
      padding: 20px;
      position: relative;
    }}
    .modal-img {{
      width: 100%;
      max-height: 360px;
      object-fit: contain;
      background: #020612;
      border-radius: 10px;
      margin-bottom: 14px;
    }}
    .modal-title {{
      font-size: 1.25rem;
      font-weight: 800;
      color: var(--gold-light);
      margin-bottom: 4px;
    }}
    .modal-tag {{
      font-size: 0.8rem;
      color: var(--gold);
      text-transform: uppercase;
      font-weight: 600;
      margin-bottom: 10px;
    }}
    .modal-desc {{
      font-size: 0.9rem;
      color: #CBD5E1;
      line-height: 1.5;
      margin-bottom: 20px;
    }}
    .modal-actions {{
      display: flex;
      gap: 10px;
    }}
    .btn-modal-call {{
      flex: 1;
      background: var(--gold);
      color: var(--bg);
      text-align: center;
      padding: 12px;
      border-radius: 8px;
      font-weight: 700;
      text-decoration: none;
    }}
    .btn-modal-close {{
      background: rgba(255,255,255,0.1);
      border: 1px solid var(--border-subtle);
      color: var(--text);
      padding: 12px 18px;
      border-radius: 8px;
      cursor: pointer;
      font-weight: 600;
    }}

    /* Admin Offline Modal Alert */
    .admin-offline-toast {{
      display: none;
      position: fixed;
      bottom: 20px;
      left: 50%;
      transform: translateX(-50%);
      background: #991b1b;
      color: #fff;
      padding: 12px 20px;
      border-radius: 10px;
      font-weight: 600;
      font-size: 0.9rem;
      box-shadow: 0 4px 16px rgba(0,0,0,0.5);
      z-index: 2000;
      text-align: center;
    }}
  </style>
</head>
<body>

  <!-- Top Offline Banner -->
  <div class="offline-banner">
    <div class="badge-offline">⚡ Saved Offline Catalogue</div>
    <div class="banner-right">
      <button type="button" class="btn-action" onclick="attemptAdminAccess()">⚙️ Admin Panel</button>
      <button type="button" class="btn-action" onclick="checkConnectionAndReload()">🔄 Retry Live</button>
      <a href="tel:+919428610384" class="btn-action btn-call">📞 Call Us</a>
    </div>
  </div>

  <div class="container">
    <!-- Header -->
    <div class="app-header">
      <img src="/static/Home_Img/favicon.png" alt="Logo" class="brand-icon" onerror="this.style.display='none'">
      <div>
        <h1 class="app-title">Image Traditional</h1>
        <p class="app-subtitle">Complete Offline Costume Rental Catalogue</p>
      </div>
    </div>

    <!-- Tabs -->
    <div class="tabs-bar">
      <button class="tab-btn active" id="tabKediya" onclick="switchTab('kediya')">🕺 Kediya (172)</button>
      <button class="tab-btn" id="tabCholi" onclick="switchTab('choli')">👗 Choli (150)</button>
      <button class="tab-btn" id="tabFancy" onclick="switchTab('fancy')">🎭 Fancy Dress (20 Categories)</button>
    </div>

    <!-- Search & Filter Card -->
    <div class="filter-section">
      <div class="search-row">
        <input type="text" id="searchInput" class="search-input" placeholder="Search costume code (e.g. K10, C25) or name..." oninput="handleSearch(this.value)">
      </div>
      <div class="pills-row" id="filterPills">
        <!-- Dynamic range/category pills -->
      </div>
    </div>

    <!-- Results Counter -->
    <div class="results-count" id="resultsCount">Loading catalogue...</div>

    <!-- Product Grid -->
    <div class="products-grid" id="productsGrid"></div>
  </div>

  <!-- Lightbox Modal -->
  <div class="modal-backdrop" id="modalBackdrop" onclick="closeModal(event)">
    <div class="modal-card" onclick="event.stopPropagation()">
      <img src="" alt="" id="modalImg" class="modal-img">
      <h2 class="modal-title" id="modalTitle"></h2>
      <div class="modal-tag" id="modalTag"></div>
      <p class="modal-desc" id="modalDesc"></p>
      <div class="modal-actions">
        <a href="tel:+919428610384" class="btn-modal-call">📞 Call to Book (+91-9428610384)</a>
        <button class="btn-modal-close" onclick="closeModal()">Close</button>
      </div>
    </div>
  </div>

  <!-- Admin Offline Alert Toast -->
  <div class="admin-offline-toast" id="adminOfflineToast">
    ⚠️ Internet connection required for Admin Panel.
  </div>

  <!-- Embedded Structured Catalogue Data -->
  <script>
    const EMBEDDED_CATALOGUE = {json.dumps(catalogue_data)};
    let activeTab = 'kediya';
    let currentFilter = 'all';
    let searchQuery = '';
    let displayedItems = [];

    // Initialize on DOM Ready
    document.addEventListener('DOMContentLoaded', () => {{
      initDataAndRender();
    }});

    // Try loading updated items from IndexedDB if synced
    async function initDataAndRender() {{
      if ('indexedDB' in window) {{
        try {{
          const req = indexedDB.open('ImageTraditionalCatalogueDB', 1);
          req.onsuccess = (e) => {{
            const db = e.target.result;
            if (db.objectStoreNames.contains('catalogue_items')) {{
              const tx = db.transaction('catalogue_items', 'readonly');
              const store = tx.objectStore('catalogue_items');
              const allReq = store.getAll();
              allReq.onsuccess = () => {{
                const items = allReq.result;
                if (items && items.length > 0) {{
                  mergeIndexedDBItems(items);
                }}
                renderCurrentView();
              }};
            }} else {{
              renderCurrentView();
            }}
          }};
          req.onerror = () => renderCurrentView();
        }} catch(e) {{
          renderCurrentView();
        }}
      }} else {{
        renderCurrentView();
      }}
    }}

    function mergeIndexedDBItems(items) {{
      const kList = [];
      const cList = [];
      const fList = [];
      items.forEach(it => {{
        if (it.category === 'kediya') {{
          kList.push({{
            code: it.name,
            name: 'Traditional Kediya ' + it.name,
            cat: 'kediya',
            img: it.img_url || ('/static/Kediya/' + it.image),
            desc: 'Hand-crafted traditional festive Kediya outfit ' + it.name + ' with authentic embroidery.'
          }});
        }} else if (it.category === 'choli') {{
          cList.push({{
            code: it.name,
            name: 'Chaniya Choli ' + it.name,
            cat: 'choli',
            img: it.img_url || ('/static/Choli/' + it.image),
            desc: 'Artisan crafted Chaniya Choli ' + it.name + ' with traditional mirror work.'
          }});
        }} else if (it.category === 'fancy') {{
          fList.push({{
            code: (it.subCategory || 'Fancy') + ' - ' + it.name,
            name: it.name,
            cat: 'fancy',
            subcat: it.subCategory,
            img: it.img_url,
            desc: it.desc || ('Stage costume representing ' + it.name)
          }});
        }}
      }});
      if (kList.length > 0) EMBEDDED_CATALOGUE.kediya = kList;
      if (cList.length > 0) EMBEDDED_CATALOGUE.choli = cList;
      if (fList.length > 0) EMBEDDED_CATALOGUE.fancy = fList;
    }}

    function switchTab(tab) {{
      activeTab = tab;
      currentFilter = 'all';
      document.getElementById('searchInput').value = '';
      searchQuery = '';

      document.getElementById('tabKediya').classList.toggle('active', tab === 'kediya');
      document.getElementById('tabCholi').classList.toggle('active', tab === 'choli');
      document.getElementById('tabFancy').classList.toggle('active', tab === 'fancy');

      renderFilterPills();
      renderCurrentView();
    }}

    function renderFilterPills() {{
      const pillsContainer = document.getElementById('filterPills');
      pillsContainer.innerHTML = '';

      if (activeTab === 'kediya') {{
        const ranges = [
          {{ id: 'all', label: 'Show All (172)' }},
          {{ id: 'k1-50', label: 'K1 - K50' }},
          {{ id: 'k51-100', label: 'K51 - K100' }},
          {{ id: 'k101-173', label: 'K101 - K173' }}
        ];
        ranges.forEach(r => {{
          const btn = document.createElement('button');
          btn.className = 'pill-btn' + (currentFilter === r.id ? ' active' : '');
          btn.textContent = r.label;
          btn.onclick = () => {{ currentFilter = r.id; renderFilterPills(); renderCurrentView(); }};
          pillsContainer.appendChild(btn);
        }});
      }} else if (activeTab === 'choli') {{
        const ranges = [
          {{ id: 'all', label: 'Show All (150)' }},
          {{ id: 'c1-50', label: 'C1 - C50' }},
          {{ id: 'c51-100', label: 'C51 - C100' }},
          {{ id: 'c101-150', label: 'C101 - C150' }}
        ];
        ranges.forEach(r => {{
          const btn = document.createElement('button');
          btn.className = 'pill-btn' + (currentFilter === r.id ? ' active' : '');
          btn.textContent = r.label;
          btn.onclick = () => {{ currentFilter = r.id; renderFilterPills(); renderCurrentView(); }};
          pillsContainer.appendChild(btn);
        }});
      }} else if (activeTab === 'fancy') {{
        const allBtn = document.createElement('button');
        allBtn.className = 'pill-btn' + (currentFilter === 'all' ? ' active' : '');
        allBtn.textContent = 'All Categories (' + EMBEDDED_CATALOGUE.fancy.length + ')';
        allBtn.onclick = () => {{ currentFilter = 'all'; renderFilterPills(); renderCurrentView(); }};
        pillsContainer.appendChild(allBtn);

        EMBEDDED_CATALOGUE.fancy_categories.forEach(cat => {{
          const btn = document.createElement('button');
          btn.className = 'pill-btn' + (currentFilter === cat.name ? ' active' : '');
          btn.textContent = cat.name + ' (' + cat.count + ')';
          btn.onclick = () => {{ currentFilter = cat.name; renderFilterPills(); renderCurrentView(); }};
          pillsContainer.appendChild(btn);
        }});
      }}
    }}

    function handleSearch(val) {{
      searchQuery = val.trim().toLowerCase();
      renderCurrentView();
    }}

    function renderCurrentView() {{
      const grid = document.getElementById('productsGrid');
      const counter = document.getElementById('resultsCount');
      let items = EMBEDDED_CATALOGUE[activeTab] || [];

      // Filter by range / category
      if (activeTab === 'kediya') {{
        if (currentFilter === 'k1-50') items = items.filter(it => getNum(it.code) >= 1 && getNum(it.code) <= 50);
        else if (currentFilter === 'k51-100') items = items.filter(it => getNum(it.code) >= 51 && getNum(it.code) <= 100);
        else if (currentFilter === 'k101-173') items = items.filter(it => getNum(it.code) >= 101 && getNum(it.code) <= 173);
      }} else if (activeTab === 'choli') {{
        if (currentFilter === 'c1-50') items = items.filter(it => getNum(it.code) >= 1 && getNum(it.code) <= 50);
        else if (currentFilter === 'c51-100') items = items.filter(it => getNum(it.code) >= 51 && getNum(it.code) <= 100);
        else if (currentFilter === 'c101-150') items = items.filter(it => getNum(it.code) >= 101 && getNum(it.code) <= 150);
      }} else if (activeTab === 'fancy') {{
        if (currentFilter !== 'all') items = items.filter(it => it.subcat === currentFilter);
      }}

      // Filter by search query
      if (searchQuery) {{
        items = items.filter(it => {{
          const codeMatch = (it.code || '').toLowerCase().includes(searchQuery);
          const nameMatch = (it.name || '').toLowerCase().includes(searchQuery);
          const descMatch = (it.desc || '').toLowerCase().includes(searchQuery);
          const subMatch = (it.subcat || '').toLowerCase().includes(searchQuery);
          return codeMatch || nameMatch || descMatch || subMatch;
        }});
      }}

      displayedItems = items;
      counter.textContent = `Showing ${{items.length}} items (Offline Saved)`;

      if (items.length === 0) {{
        grid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 40px; color: #94A3B8;">No costumes matching your search query. Try another code or keyword.</div>';
        return;
      }}

      grid.innerHTML = items.map((it, idx) => `
        <div class="product-card" onclick="openModal(${{idx}})">
          <div class="img-wrap">
            <img src="${{it.img}}" alt="${{it.name}}" loading="lazy" onerror="this.onerror=null; if('${{it.fallback_img || ''}}') this.src='${{it.fallback_img}}'; else this.src='/static/Home_Img/favicon.png';">
          </div>
          <div class="card-body">
            <div class="card-code">${{it.code}}</div>
            <div class="card-tag">${{it.subcat || it.cat.toUpperCase()}}</div>
            <div class="card-desc">${{it.desc}}</div>
            <div class="btn-view">Inspect Outfit</div>
          </div>
        </div>
      `).join('');
    }}

    function getNum(str) {{
      const m = (str || '').match(/\\d+/);
      return m ? parseInt(m[0], 10) : 0;
    }}

    function openModal(idx) {{
      const item = displayedItems[idx];
      if (!item) return;

      document.getElementById('modalImg').src = item.img;
      document.getElementById('modalImg').onerror = function() {{
        this.src = item.fallback_img || '/static/Home_Img/favicon.png';
      }};
      document.getElementById('modalTitle').textContent = item.name || item.code;
      document.getElementById('modalTag').textContent = item.subcat ? `Fancy Dress / ${{item.subcat}}` : (item.cat === 'kediya' ? 'Festive Kediya' : 'Chaniya Choli');
      document.getElementById('modalDesc').textContent = item.desc;

      document.getElementById('modalBackdrop').style.display = 'flex';
      try {{
        window.history.pushState({{ modalOpen: true }}, '');
      }} catch (e) {{}}
    }}

    function closeModal() {{
      const backdrop = document.getElementById('modalBackdrop');
      if (backdrop && backdrop.style.display !== 'none') {{
        backdrop.style.display = 'none';
        if (window.history.state && window.history.state.modalOpen) {{
          window.history.back();
        }}
      }}
    }}

    window.addEventListener('popstate', () => {{
      const backdrop = document.getElementById('modalBackdrop');
      if (backdrop && backdrop.style.display === 'flex') {{
        backdrop.style.display = 'none';
      }}
    }});

    function attemptAdminAccess() {{
      if (navigator.onLine) {{
        window.location.href = '/admin';
      }} else {{
        const toast = document.getElementById('adminOfflineToast');
        toast.style.display = 'block';
        setTimeout(() => toast.style.display = 'none', 3500);
      }}
    }}

    function checkConnectionAndReload() {{
      if (navigator.onLine) {{
        window.location.href = '/app';
      }} else {{
        alert("Device is still offline. The offline catalogue remains fully accessible.");
      }}
    }}

    window.addEventListener('online', () => {{
      const toast = document.getElementById('adminOfflineToast');
      toast.style.background = '#047857';
      toast.textContent = '✨ Connection restored! Tap Retry Live to connect to the live server.';
      toast.style.display = 'block';
    }});

    // Initialize filter pills on load
    renderFilterPills();
  </script>
</body>
</html>"""

    # Save to website/static/offline.html
    static_offline = os.path.join('website', 'static', 'offline.html')
    with open(static_offline, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"[OK] Wrote rich offline catalogue to {static_offline} ({len(html)} bytes)")

    # Save to android/app/src/main/assets/offline_catalogue.html
    assets_dir = os.path.join('android', 'app', 'src', 'main', 'assets')
    os.makedirs(assets_dir, exist_ok=True)
    android_offline = os.path.join(assets_dir, 'offline_catalogue.html')
    with open(android_offline, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"[OK] Wrote bundled Android offline catalogue to {android_offline} ({len(html)} bytes)")

if __name__ == '__main__':
    generate_offline_catalogue_html()
