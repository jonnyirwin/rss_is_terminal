(() => {
  // Guard against double-injection
  if (window.__rit_scraper_injected) {
    // Already injected — just listen for toggle
    return;
  }
  window.__rit_scraper_injected = true;

  // ---- State ----

  const state = {
    articleSelector: null,
    fields: {},
    paginationSelector: null,
    pickingField: null, // "article", "pagination", or field name
  };

  let panelHost = null;
  let shadow = null;
  let overlay = null;
  let label = null;
  let hoveredEl = null;

  // ---- Panel HTML ----

  const PANEL_CSS = `
    :host {
      all: initial;
      position: fixed;
      top: 0;
      right: 0;
      width: 340px;
      height: 100vh;
      z-index: 2147483646;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
      font-size: 13px;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    .feeds-detected {
      padding: 10px 14px;
      border-bottom: 1px solid #0f3460;
      background: #16213e;
    }
    .feeds-detected h3 {
      font-size: 12px; color: #00d2ff; margin-bottom: 6px;
      display: flex; align-items: center; gap: 6px;
    }
    .feeds-detected .feed-count {
      font-size: 10px; color: #8899aa; font-weight: normal;
    }
    .feed-item {
      display: flex; align-items: center; gap: 6px;
      padding: 5px 0; border-bottom: 1px solid #0a0a1a;
    }
    .feed-item:last-child { border-bottom: none; }
    .feed-info { flex: 1; min-width: 0; overflow: hidden; }
    .feed-title-text {
      font-size: 12px; color: #e0e0e0; font-weight: 500;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .feed-url-text {
      font-size: 10px; color: #666; font-family: monospace;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .feed-type-badge {
      font-size: 9px; padding: 1px 5px; border-radius: 3px;
      font-weight: 600; flex-shrink: 0;
    }
    .feed-type-badge.rss { background: #e9a045; color: #1a1a2e; }
    .feed-type-badge.atom { background: #7b61ff; color: #fff; }
    .feed-type-badge.json { background: #00875a; color: #fff; }
    .feed-add-btn {
      background: #00875a; color: #fff; border: none;
      padding: 3px 10px; border-radius: 3px; cursor: pointer;
      font-size: 10px; font-weight: 600; flex-shrink: 0;
    }
    .feed-add-btn:hover { background: #00a06a; }
    .feed-add-btn:disabled { background: #555; color: #888; cursor: not-allowed; }
    .feed-add-btn.added { background: #0f3460; }
    .no-feeds { font-size: 11px; color: #555; font-style: italic; }
    .category-picker {
      margin: 6px 0; display: flex; align-items: center; gap: 6px;
    }
    .category-picker label { font-size: 11px; color: #8899aa; flex-shrink: 0; }
    .category-picker select {
      flex: 1; background: #0a0a1a; border: 1px solid #0f3460;
      color: #e0e0e0; padding: 3px 6px; border-radius: 3px;
      font-size: 11px; font-family: inherit;
    }
    .category-picker select:focus { border-color: #00d2ff; outline: none; }
    .scraper-divider {
      padding: 8px 14px; font-size: 11px; color: #555;
      text-align: center; border-bottom: 1px solid #0f3460;
      text-transform: uppercase; letter-spacing: 1px;
    }
    .panel {
      width: 100%;
      height: 100%;
      background: #1a1a2e;
      color: #e0e0e0;
      border-left: 2px solid #0f3460;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
    }
    header {
      background: #16213e;
      padding: 10px 14px;
      border-bottom: 1px solid #0f3460;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    header .left { display: flex; align-items: center; gap: 8px; }
    header h1 { font-size: 14px; color: #00d2ff; font-weight: 600; }
    .close-btn {
      background: none; border: none; color: #8899aa; font-size: 18px;
      cursor: pointer; padding: 2px 6px; line-height: 1;
    }
    .close-btn:hover { color: #e94560; }

    .step {
      padding: 12px 14px;
      border-bottom: 1px solid #0f3460;
    }
    .step.inactive { opacity: 0.4; pointer-events: none; }
    .step.active { background: #16213e; }
    .step.done { opacity: 0.8; }
    .step-header {
      display: flex; align-items: center; gap: 8px; margin-bottom: 6px;
    }
    .step-num {
      background: #0f3460; color: #00d2ff;
      width: 22px; height: 22px; border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      font-size: 11px; font-weight: 700; flex-shrink: 0;
    }
    .step.done .step-num { background: #00875a; color: #fff; }
    .step-title { font-weight: 600; font-size: 13px; }
    .step-desc { color: #8899aa; font-size: 11px; margin-left: 30px; }
    .step-value {
      font-family: monospace; font-size: 11px; color: #00d2ff;
      background: #0a0a1a; padding: 3px 6px; border-radius: 3px;
      margin: 4px 0 0 30px; word-break: break-all;
    }

    .field-row {
      display: flex; align-items: center; gap: 6px; margin: 4px 0 4px 30px;
    }
    .field-label { font-size: 11px; color: #8899aa; width: 55px; flex-shrink: 0; }
    .field-value {
      font-family: monospace; font-size: 11px; color: #00d2ff;
      background: #0a0a1a; padding: 2px 5px; border-radius: 3px;
      flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }
    .field-value.empty { color: #555; font-style: italic; }
    .field-btn {
      background: #0f3460; color: #00d2ff; border: none;
      padding: 2px 8px; border-radius: 3px; cursor: pointer; font-size: 10px; flex-shrink: 0;
    }
    .field-btn:hover { background: #1a4a8a; }
    .field-btn.picking { background: #e94560; color: #fff; }

    .config-section {
      padding: 12px 14px; border-bottom: 1px solid #0f3460;
    }
    .config-row {
      display: flex; align-items: center; gap: 8px; margin-bottom: 6px;
    }
    .config-row label { font-size: 11px; color: #8899aa; width: 70px; flex-shrink: 0; }
    .config-row input[type="text"],
    .config-row input[type="number"] {
      flex: 1; background: #0a0a1a; border: 1px solid #0f3460;
      color: #e0e0e0; padding: 4px 6px; border-radius: 3px;
      font-size: 12px; font-family: inherit;
    }
    .config-row input:focus { border-color: #00d2ff; outline: none; }
    .config-row input[type="checkbox"] { width: 14px; height: 14px; }

    .actions {
      padding: 12px 14px; display: flex; gap: 8px;
    }
    .btn {
      flex: 1; padding: 8px 12px; border: none; border-radius: 4px;
      font-size: 12px; font-weight: 600; cursor: pointer; font-family: inherit;
    }
    .btn-primary { background: #00d2ff; color: #1a1a2e; }
    .btn-primary:hover { background: #33ddff; }
    .btn-primary:disabled { background: #555; color: #888; cursor: not-allowed; }
    .btn-secondary { background: #0f3460; color: #e0e0e0; }
    .btn-secondary:hover { background: #1a4a8a; }
    .btn-danger { background: #e94560; color: #fff; }
    .btn-danger:hover { background: #ff5577; }

    .status {
      padding: 8px 14px; font-size: 11px; color: #00875a; text-align: center;
    }
    .status.error { color: #e94560; }

    .preview-section { display: none; padding: 10px 14px; border-bottom: 1px solid #0f3460; }
    .preview-section.visible { display: block; }
    .preview-section h3 { font-size: 12px; color: #8899aa; margin-bottom: 6px; }
    .preview-count { font-size: 12px; color: #00d2ff; margin-bottom: 4px; }
    .preview-item {
      background: #0a0a1a; padding: 6px 8px; border-radius: 3px;
      margin-bottom: 4px; font-size: 11px;
    }
    .preview-item .ptitle { color: #e0e0e0; font-weight: 600; }
    .preview-item .pmeta { color: #666; font-size: 10px; }

    .js-hint {
      display: none; margin-left: 78px;
      font-size: 10px; color: #e9a045;
    }
    .js-hint.visible { display: block; }

    .btn-row { margin: 6px 0 0 30px; display: flex; gap: 6px; }
  `;

  const PANEL_HTML = `
    <div class="panel">
      <header>
        <div class="left">
          <span style="font-size:18px">&#x1f4e1;</span>
          <h1>Scraper Config Builder</h1>
        </div>
        <button class="close-btn" id="rit-close">&times;</button>
      </header>

      <!-- Detected feeds -->
      <div class="feeds-detected" id="rit-feeds-section" style="display:none">
        <h3>
          <span>&#x1f4e1;</span> Feeds detected
          <span class="feed-count" id="rit-feed-count"></span>
        </h3>
        <div class="category-picker" id="rit-feed-category-row" style="display:none">
          <label>Category:</label>
          <select id="rit-feed-category">
            <option value="">(none)</option>
          </select>
        </div>
        <div id="rit-feed-list"></div>
      </div>

      <div class="scraper-divider" id="rit-scraper-divider" style="display:none">
        or build a custom scraper
      </div>

      <!-- Step 1 -->
      <div class="step active" id="rit-step1">
        <div class="step-header">
          <span class="step-num">1</span>
          <span class="step-title">Select an article element</span>
        </div>
        <div class="step-desc">Click any single article/post on the page</div>
        <div class="step-value" id="rit-article-sel" style="display:none"></div>
        <div class="btn-row">
          <button class="field-btn" id="rit-pick-article">Pick element</button>
        </div>
      </div>

      <!-- Step 2 -->
      <div class="step inactive" id="rit-step2">
        <div class="step-header">
          <span class="step-num">2</span>
          <span class="step-title">Select fields within article</span>
        </div>
        <div class="step-desc">Pick elements for each field (title required)</div>
        <div class="field-row">
          <span class="field-label">title</span>
          <span class="field-value empty" id="rit-val-title">not set</span>
          <button class="field-btn" data-field="title">pick</button>
        </div>
        <div class="field-row">
          <span class="field-label">url</span>
          <span class="field-value empty" id="rit-val-url">not set</span>
          <button class="field-btn" data-field="url">pick</button>
        </div>
        <div class="field-row">
          <span class="field-label">author</span>
          <span class="field-value empty" id="rit-val-author">not set</span>
          <button class="field-btn" data-field="author">pick</button>
        </div>
        <div class="field-row">
          <span class="field-label">date</span>
          <span class="field-value empty" id="rit-val-date">not set</span>
          <button class="field-btn" data-field="date">pick</button>
        </div>
        <div class="field-row">
          <span class="field-label">summary</span>
          <span class="field-value empty" id="rit-val-summary">not set</span>
          <button class="field-btn" data-field="summary">pick</button>
        </div>
      </div>

      <!-- Step 3: Pagination -->
      <div class="step inactive" id="rit-step3">
        <div class="step-header">
          <span class="step-num">3</span>
          <span class="step-title">Pagination (optional)</span>
        </div>
        <div class="step-desc">Pick the "next page" link</div>
        <div class="field-row">
          <span class="field-label">next link</span>
          <span class="field-value empty" id="rit-val-pagination">not set</span>
          <button class="field-btn" data-field="pagination">pick</button>
          <button class="field-btn" id="rit-clear-pagination" style="display:none">clear</button>
        </div>
        <div class="field-row" id="rit-max-pages-row" style="display:none">
          <span class="field-label">max pages</span>
          <input type="number" id="rit-max-pages" value="3" min="1" max="20"
            style="width:50px; background:#0a0a1a; border:1px solid #0f3460;
                   color:#e0e0e0; padding:2px 5px; border-radius:3px; font-size:11px;">
        </div>
      </div>

      <!-- Config -->
      <div class="config-section" id="rit-config" style="display:none">
        <div class="config-row">
          <label>Name</label>
          <input type="text" id="rit-feed-name" placeholder="Feed name">
        </div>
        <div class="config-row" id="rit-scraper-category-row" style="display:none">
          <label>Category</label>
          <select id="rit-scraper-category" style="flex:1; background:#0a0a1a; border:1px solid #0f3460; color:#e0e0e0; padding:4px 6px; border-radius:3px; font-size:12px;">
            <option value="">(none)</option>
          </select>
        </div>
        <div class="config-row">
          <label>JS render</label>
          <input type="checkbox" id="rit-js-render">
          <span style="font-size:11px; color:#8899aa">Playwright for JS sites</span>
        </div>
        <div class="js-hint" id="rit-js-hint">Page may use JS rendering</div>
        <div class="config-row" id="rit-wait-for-row" style="display:none">
          <label>Wait for</label>
          <input type="text" id="rit-wait-for" placeholder="CSS selector (optional)">
        </div>
      </div>

      <!-- Preview -->
      <div class="preview-section" id="rit-preview">
        <h3>Preview</h3>
        <div class="preview-count" id="rit-preview-count"></div>
        <div id="rit-preview-items"></div>
      </div>

      <!-- Actions -->
      <div class="actions">
        <button class="btn btn-secondary" id="rit-btn-preview" disabled>Preview</button>
        <button class="btn btn-primary" id="rit-btn-save" disabled>Add to app</button>
        <button class="btn btn-danger" id="rit-btn-reset">Reset</button>
      </div>
      <div class="actions" style="padding-top:0">
        <button class="btn btn-secondary" id="rit-btn-download" disabled style="font-size:11px">Download JSON instead</button>
      </div>

      <div class="status" id="rit-status"></div>
    </div>
  `;

  // ---- Panel lifecycle ----

  function createPanel() {
    if (panelHost) return;
    panelHost = document.createElement("div");
    panelHost.id = "__rit-panel-host";
    shadow = panelHost.attachShadow({ mode: "closed" });

    const style = document.createElement("style");
    style.textContent = PANEL_CSS;
    shadow.appendChild(style);

    const container = document.createElement("div");
    container.innerHTML = PANEL_HTML;
    shadow.appendChild(container);

    document.body.appendChild(panelHost);

    // Push page content left so panel doesn't cover it
    document.documentElement.style.marginRight = "340px";

    bindEvents();
    loadCategories();
    detectFeeds();
    detectJSRendering();
  }

  function removePanel() {
    stopPicking();
    if (panelHost) {
      panelHost.remove();
      panelHost = null;
      shadow = null;
    }
    document.documentElement.style.marginRight = "";
  }

  function togglePanel() {
    if (panelHost) {
      removePanel();
    } else {
      createPanel();
    }
  }

  // ---- Overlay ----

  function createOverlay() {
    if (overlay) return;
    overlay = document.createElement("div");
    overlay.id = "__rit-overlay";
    overlay.style.cssText = `
      position: absolute; pointer-events: none; z-index: 2147483645;
      border: 2px solid #00d2ff; background: rgba(0, 210, 255, 0.12);
      border-radius: 3px; transition: all 0.08s ease;
    `;
    document.body.appendChild(overlay);
  }

  function removeOverlay() {
    if (overlay) { overlay.remove(); overlay = null; }
  }

  function createLabel() {
    if (label) return;
    label = document.createElement("div");
    label.style.cssText = `
      position: fixed; top: 8px; left: 50%; transform: translateX(-50%);
      z-index: 2147483647; background: #1a1a2e; color: #00d2ff;
      font-family: monospace; font-size: 13px; padding: 6px 16px;
      border-radius: 6px; border: 1px solid #00d2ff; pointer-events: none;
      box-shadow: 0 4px 12px rgba(0,0,0,0.5);
    `;
    document.body.appendChild(label);
  }

  function removeLabel() {
    if (label) { label.remove(); label = null; }
  }

  function updateLabel() {
    if (!label) return;
    const labels = {
      article: "Click an article/post element",
      pagination: "Click the 'next page' link",
      title: "Click the title", url: "Click the link",
      author: "Click the author", date: "Click the date",
      summary: "Click the summary/excerpt",
    };
    label.textContent = labels[state.pickingField] || `Pick: ${state.pickingField}`;
  }

  function positionOverlay(el) {
    if (!overlay || !el) return;
    const rect = el.getBoundingClientRect();
    overlay.style.top = (rect.top + window.scrollY) + "px";
    overlay.style.left = (rect.left + window.scrollX) + "px";
    overlay.style.width = rect.width + "px";
    overlay.style.height = rect.height + "px";
    const colors = {
      article: ["#00d2ff", "rgba(0,210,255,0.12)"],
      pagination: ["#e9a045", "rgba(233,160,69,0.12)"],
    };
    const [border, bg] = colors[state.pickingField] || ["#e94560", "rgba(233,69,96,0.12)"];
    overlay.style.borderColor = border;
    overlay.style.background = bg;
  }

  // ---- CSS Selector generation ----

  function selectorSegment(el) {
    const tag = el.tagName.toLowerCase();
    if (el.id && /^[a-zA-Z][\w-]*$/.test(el.id) && !looksGenerated(el.id)) {
      return `#${CSS.escape(el.id)}`;
    }
    const classes = Array.from(el.classList)
      .filter(c => !looksGenerated(c) && /^[a-zA-Z]/.test(c))
      .slice(0, 3);
    if (classes.length > 0) {
      return tag + classes.map(c => "." + CSS.escape(c)).join("");
    }
    const parent = el.parentElement;
    if (parent) {
      const siblings = Array.from(parent.children).filter(s => s.tagName === el.tagName);
      if (siblings.length > 1) {
        return `${tag}:nth-of-type(${siblings.indexOf(el) + 1})`;
      }
    }
    return tag;
  }

  function looksGenerated(str) {
    if (str.length > 24) return true;
    if (/[0-9a-f]{8,}/i.test(str)) return true;
    if (/^[a-z]{1,3}\d{4,}/.test(str)) return true;
    return false;
  }

  function generateSelector(el, relativeTo = null) {
    const root = relativeTo || document.documentElement;
    const path = [];
    let current = el;
    while (current && current !== root && current !== document.documentElement) {
      path.unshift(selectorSegment(current));
      const candidate = path.join(" > ");
      try {
        const base = relativeTo || document;
        const matches = base.querySelectorAll(candidate);
        if (matches.length === 1 && matches[0] === el) {
          return simplifySelector(candidate, el, base);
        }
      } catch (e) { /* keep building */ }
      current = current.parentElement;
    }
    return simplifySelector(path.join(" > "), el, relativeTo || document);
  }

  function simplifySelector(sel, targetEl, base) {
    const parts = sel.split(" > ");
    for (let i = parts.length - 1; i >= 0; i--) {
      const candidate = parts.slice(i).join(" ");
      try {
        const matches = base.querySelectorAll(candidate);
        if (matches.length === 1 && matches[0] === targetEl) return candidate;
      } catch (e) { continue; }
    }
    if (parts.length >= 2) {
      const candidate = parts[0] + " " + parts[parts.length - 1];
      try {
        const matches = base.querySelectorAll(candidate);
        if (matches.length === 1 && matches[0] === targetEl) return candidate;
      } catch (e) { /* fall through */ }
    }
    return sel;
  }

  function generateArticleSelector(el) {
    const tag = el.tagName.toLowerCase();
    const parent = el.parentElement;
    if (!parent) return tag;

    const siblings = Array.from(parent.children).filter(s => s.tagName === el.tagName);
    if (el.classList.length > 0) {
      const classScores = {};
      for (const cls of el.classList) {
        if (looksGenerated(cls)) continue;
        const count = siblings.filter(s => s.classList.contains(cls)).length;
        if (count >= 2) classScores[cls] = count;
      }
      const bestClasses = Object.entries(classScores)
        .sort((a, b) => b[1] - a[1]).slice(0, 2).map(([cls]) => cls);
      if (bestClasses.length > 0) {
        const sel = tag + bestClasses.map(c => "." + CSS.escape(c)).join("");
        if (document.querySelectorAll(sel).length >= 2) return sel;
      }
    }
    const parentSeg = selectorSegment(parent);
    const sel = `${parentSeg} > ${tag}`;
    try { if (document.querySelectorAll(sel).length >= 2) return sel; } catch (e) { /* */ }
    return selectorSegment(el);
  }

  function generateFieldSelector(el, articleEl, fieldName) {
    let sel = generateSelector(el, articleEl);
    if (fieldName === "url") {
      const link = el.tagName === "A" ? el : el.querySelector("a");
      if (link) return (link === el ? sel : generateSelector(link, articleEl)) + " @href";
    }
    if (fieldName === "date") {
      const time = el.tagName === "TIME" ? el : el.querySelector("time");
      if (time && time.getAttribute("datetime"))
        return (time === el ? sel : generateSelector(time, articleEl)) + " @datetime";
    }
    if (fieldName === "title") {
      const link = el.tagName === "A" ? el : el.querySelector("a");
      if (link && link !== el) return generateSelector(link, articleEl);
    }
    return sel;
  }

  function generatePaginationSelector(el) {
    const link = el.tagName === "A" ? el : el.closest("a");
    if (link) return generateSelector(link) + " @href";
    return generateSelector(el);
  }

  // ---- JS detection ----

  function detectJSRendering() {
    const root = document.getElementById("__next")
      || document.getElementById("__nuxt")
      || document.getElementById("app")
      || document.querySelector("[data-reactroot]")
      || document.querySelector("[ng-app]")
      || document.querySelector("[data-server-rendered]");
    let signals = 0;
    if (root) signals++;
    for (const ns of document.querySelectorAll("noscript")) {
      if (ns.textContent.toLowerCase().includes("javascript")) { signals++; break; }
    }
    const scripts = document.querySelectorAll("script[src]");
    const bodyText = (document.body.innerText || "").trim();
    if (scripts.length > 5 && bodyText.length < 500) signals++;

    if (signals >= 1 && shadow) {
      const hint = shadow.getElementById("rit-js-hint");
      if (hint) hint.classList.add("visible");
    }
  }

  // ---- Category loading ----

  let categories = [];

  function loadCategories() {
    chrome.runtime.sendMessage({ action: "nativeGetCategories" }, (response) => {
      if (!response || !response.categories || response.categories.length === 0) return;
      categories = response.categories;
      populateCategoryDropdowns();
    });
  }

  function populateCategoryDropdowns() {
    if (!shadow) return;
    const selects = [
      shadow.getElementById("rit-feed-category"),
      shadow.getElementById("rit-scraper-category"),
    ];
    for (const sel of selects) {
      if (!sel) continue;
      // Keep the (none) option, add categories
      sel.innerHTML = '<option value="">(none)</option>';
      for (const cat of categories) {
        const opt = document.createElement("option");
        opt.value = cat.id;
        opt.textContent = cat.name;
        sel.appendChild(opt);
      }
    }
    // Show category rows if we have categories
    if (categories.length > 0) {
      const feedCatRow = shadow.getElementById("rit-feed-category-row");
      if (feedCatRow) feedCatRow.style.display = "";
      const scraperCatRow = shadow.getElementById("rit-scraper-category-row");
      if (scraperCatRow) scraperCatRow.style.display = "";
    }
  }

  function getSelectedFeedCategoryIds() {
    if (!shadow) return [];
    const sel = shadow.getElementById("rit-feed-category");
    if (!sel || !sel.value) return [];
    return [parseInt(sel.value, 10)];
  }

  function getSelectedScraperCategoryIds() {
    if (!shadow) return [];
    const sel = shadow.getElementById("rit-scraper-category");
    if (!sel || !sel.value) return [];
    return [parseInt(sel.value, 10)];
  }

  // ---- Feed detection ----

  function detectFeeds() {
    if (!shadow) return;

    const feeds = [];

    // Check <link> tags for RSS/Atom/JSON feeds
    const linkEls = document.querySelectorAll(
      'link[rel="alternate"][type="application/rss+xml"], ' +
      'link[rel="alternate"][type="application/atom+xml"], ' +
      'link[rel="alternate"][type="application/feed+json"], ' +
      'link[rel="alternate"][type="application/json"]'
    );

    for (const link of linkEls) {
      const href = link.href || link.getAttribute("href");
      if (!href) continue;
      const url = new URL(href, location.href).href;
      const type = link.type || "";
      let badge = "rss";
      if (type.includes("atom")) badge = "atom";
      else if (type.includes("json")) badge = "json";

      feeds.push({
        title: link.title || url.split("/").pop() || "Feed",
        url,
        badge,
      });
    }

    // Also check for common feed URL patterns in <a> tags
    if (feeds.length === 0) {
      const feedPatterns = /\/(feed|rss|atom|feeds?)\/?(\?.*)?$/i;
      const seen = new Set();
      for (const a of document.querySelectorAll('a[href]')) {
        const href = a.href;
        if (feedPatterns.test(href) && !seen.has(href)) {
          seen.add(href);
          feeds.push({
            title: a.textContent.trim() || href.split("/").pop() || "Feed",
            url: href,
            badge: "rss",
          });
        }
      }
    }

    const section = shadow.getElementById("rit-feeds-section");
    const divider = shadow.getElementById("rit-scraper-divider");
    const countEl = shadow.getElementById("rit-feed-count");
    const listEl = shadow.getElementById("rit-feed-list");

    if (feeds.length === 0) {
      section.style.display = "none";
      divider.style.display = "none";
      return;
    }

    section.style.display = "";
    divider.style.display = "";
    countEl.textContent = `(${feeds.length})`;
    listEl.innerHTML = "";

    for (const feed of feeds) {
      const item = document.createElement("div");
      item.className = "feed-item";
      item.innerHTML = `
        <div class="feed-info">
          <div class="feed-title-text">${escapeHtml(feed.title)}</div>
          <div class="feed-url-text">${escapeHtml(feed.url)}</div>
        </div>
        <span class="feed-type-badge ${feed.badge}">${feed.badge.toUpperCase()}</span>
        <button class="feed-add-btn">Add</button>
      `;

      const btn = item.querySelector(".feed-add-btn");
      btn.addEventListener("click", () => {
        btn.disabled = true;
        btn.textContent = "Adding...";

        chrome.runtime.sendMessage(
          { action: "nativeAddFeed", url: feed.url, title: feed.title, category_ids: getSelectedFeedCategoryIds() },
          (response) => {
            if (!response || response.nativeNotInstalled) {
              btn.disabled = false;
              btn.textContent = "Add";
              setStatus("Native host not installed. Run: make native-host", true);
              return;
            }
            if (response.error) {
              btn.disabled = false;
              btn.textContent = "Add";
              setStatus("Error: " + response.error, true);
              return;
            }
            btn.textContent = "Added!";
            btn.className = "feed-add-btn added";
            setStatus(response.message || "Feed added! Refresh RSS is Terminal to see it.");
          }
        );
      });

      listEl.appendChild(item);
    }
  }

  // ---- Picking ----

  function startPicking(mode) {
    state.pickingField = mode;
    hoveredEl = null;
    createOverlay();
    createLabel();
    updateLabel();

    document.addEventListener("mousemove", onMouseMove, true);
    document.addEventListener("click", onClick, true);
    document.addEventListener("keydown", onKeyDown, true);
    updateUI();
  }

  function stopPicking() {
    state.pickingField = null;
    hoveredEl = null;
    removeOverlay();
    removeLabel();
    document.removeEventListener("mousemove", onMouseMove, true);
    document.removeEventListener("click", onClick, true);
    document.removeEventListener("keydown", onKeyDown, true);
    updateUI();
  }

  function isInsidePanel(el) {
    // Check if the click target is inside our shadow host
    let node = el;
    while (node) {
      if (node === panelHost) return true;
      node = node.parentNode || node.host;
    }
    return false;
  }

  function onMouseMove(e) {
    if (!state.pickingField) return;
    if (isInsidePanel(e.target)) return;
    const target = e.target;
    if (target === overlay || target === label) return;

    // Constrain field picks to within an article element
    if (state.pickingField !== "article" && state.pickingField !== "pagination" && state.articleSelector) {
      if (!target.closest(state.articleSelector)) return;
    }

    if (target !== hoveredEl) {
      hoveredEl = target;
      positionOverlay(target);
    }
  }

  function onClick(e) {
    if (!state.pickingField) return;
    if (isInsidePanel(e.target)) return;

    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();

    const target = hoveredEl || e.target;
    if (target === overlay || target === label) return;

    const mode = state.pickingField;
    let selector;

    if (mode === "article") {
      selector = generateArticleSelector(target);
      state.articleSelector = selector;
    } else if (mode === "pagination") {
      selector = generatePaginationSelector(target);
      state.paginationSelector = selector;
    } else {
      const articleEl = state.articleSelector ? target.closest(state.articleSelector) : target.parentElement;
      selector = generateFieldSelector(target, articleEl, mode);
      state.fields[mode] = selector;
    }

    stopPicking();

    // Auto-set feed name on first article pick
    if (mode === "article" && shadow) {
      const nameInput = shadow.getElementById("rit-feed-name");
      if (nameInput && !nameInput.value) {
        nameInput.value = document.title || "";
      }
    }
  }

  function onKeyDown(e) {
    if (!state.pickingField) return;
    if (e.key === "Escape") {
      e.preventDefault();
      stopPicking();
    }
  }

  // ---- Preview ----

  function parseFieldSel(s) {
    const parts = s.split(" @");
    if (parts.length === 2) return { css: parts[0].trim(), attr: parts[1].trim() };
    return { css: s.trim(), attr: null };
  }

  function extractPreview() {
    if (!state.articleSelector) return { items: [] };
    const articleEls = document.querySelectorAll(state.articleSelector);
    const items = [];
    for (const articleEl of articleEls) {
      const item = {};
      for (const [field, selectorStr] of Object.entries(state.fields)) {
        const { css, attr } = parseFieldSel(selectorStr);
        const el = articleEl.querySelector(css);
        if (el) item[field] = attr ? el.getAttribute(attr) : el.textContent.trim();
      }
      items.push(item);
    }
    return { items };
  }

  // ---- Raw HTML validation ----
  // Fetches the page source (as the scraper would) and tests selectors against it.
  // This catches selectors that rely on JS-added classes/attributes.

  async function validateAgainstRawHTML() {
    const jsRender = shadow.getElementById("rit-js-render").checked;
    if (jsRender) return null; // JS render mode uses a browser too, so no mismatch

    try {
      const resp = await fetch(location.href);
      const html = await resp.text();

      const parser = new DOMParser();
      const doc = parser.parseFromString(html, "text/html");

      const rawArticles = doc.querySelectorAll(state.articleSelector);
      const liveArticles = document.querySelectorAll(state.articleSelector);

      if (rawArticles.length === 0 && liveArticles.length > 0) {
        // Article selector doesn't work in raw HTML — try to find a better one
        const suggestion = suggestRawSelector(doc);
        return {
          problem: "article",
          message: `Article selector "${state.articleSelector}" matches ${liveArticles.length} items in the browser but 0 in the raw HTML (the class is added by JavaScript).`,
          suggestion,
        };
      }

      // Check field selectors within articles
      if (rawArticles.length > 0) {
        const rawArticle = rawArticles[0];
        const liveArticle = liveArticles[0];
        for (const [field, selectorStr] of Object.entries(state.fields)) {
          const { css } = parseFieldSel(selectorStr);
          const rawMatch = rawArticle.querySelector(css);
          const liveMatch = liveArticle.querySelector(css);
          if (!rawMatch && liveMatch) {
            return {
              problem: field,
              message: `Field "${field}" selector "${css}" works in browser but not in raw HTML.`,
            };
          }
        }
      }

      return null; // All good
    } catch (e) {
      return null; // Can't validate, skip
    }
  }

  function suggestRawSelector(doc) {
    // Try to find the right article container using the field selectors we already have
    // Look for a common parent of elements matching our field selectors
    const titleSel = state.fields.title;
    if (!titleSel) return null;

    const { css } = parseFieldSel(titleSel);
    const titleEls = doc.querySelectorAll(css);
    if (titleEls.length === 0) return null;

    // Find the common repeating parent
    const parents = [];
    for (const el of titleEls) {
      let p = el.parentElement;
      // Walk up to find a reasonable container (li, article, div, section)
      while (p && !["li", "article", "section"].includes(p.tagName.toLowerCase())) {
        if (p.tagName.toLowerCase() === "div" && p.parentElement) {
          // Check if parent has multiple similar children
          const sibs = Array.from(p.parentElement.children).filter(
            s => s.tagName === p.tagName
          );
          if (sibs.length >= 2) break;
        }
        p = p.parentElement;
      }
      if (p) parents.push(p);
    }

    if (parents.length < 2) return null;

    // Generate a selector for this container
    const first = parents[0];
    const tag = first.tagName.toLowerCase();

    // Try parent > tag
    const grandparent = first.parentElement;
    if (grandparent) {
      const gpSeg = selectorSegment(grandparent);
      const candidate = `${gpSeg} > ${tag}`;
      try {
        if (doc.querySelectorAll(candidate).length >= 2) return candidate;
      } catch (e) { /* */ }
    }

    // Try tag with shared classes
    if (first.classList.length > 0) {
      for (const cls of first.classList) {
        if (looksGenerated(cls)) continue;
        const candidate = `${tag}.${CSS.escape(cls)}`;
        try {
          if (doc.querySelectorAll(candidate).length >= 2) return candidate;
        } catch (e) { /* */ }
      }
    }

    return `${selectorSegment(grandparent)} > ${tag}`;
  }

  // ---- Config builder ----

  function buildConfig() {
    const name = shadow.getElementById("rit-feed-name").value.trim();
    const jsRender = shadow.getElementById("rit-js-render").checked;
    const waitFor = shadow.getElementById("rit-wait-for").value.trim();

    const fields = {};
    for (const [key, val] of Object.entries(state.fields)) {
      if (val) fields[key] = val;
    }

    const config = {
      name: name || location.hostname,
      url: location.href,
      js_render: jsRender,
      article_selector: state.articleSelector,
      fields,
    };

    if (jsRender) config.wait_for = waitFor || state.articleSelector;

    if (state.paginationSelector) {
      const maxPages = parseInt(shadow.getElementById("rit-max-pages").value, 10) || 3;
      config.pagination = { next_selector: state.paginationSelector, max_pages: maxPages };
    }

    return config;
  }

  function escapeHtml(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  // ---- UI update ----

  function updateUI() {
    if (!shadow) return;

    const step1 = shadow.getElementById("rit-step1");
    const step2 = shadow.getElementById("rit-step2");
    const step3 = shadow.getElementById("rit-step3");
    const config = shadow.getElementById("rit-config");

    if (state.articleSelector) {
      step1.className = "step done";
      step2.className = "step active";
      step3.className = state.fields.title ? "step active" : "step inactive";
      config.style.display = "";
    } else {
      step1.className = "step active";
      step2.className = "step inactive";
      step3.className = "step inactive";
      config.style.display = "none";
    }

    // Article selector display
    const asel = shadow.getElementById("rit-article-sel");
    if (state.articleSelector) {
      asel.textContent = state.articleSelector;
      asel.style.display = "";
    } else {
      asel.style.display = "none";
    }

    // Field values
    for (const field of ["title", "url", "author", "date", "summary"]) {
      const el = shadow.getElementById(`rit-val-${field}`);
      if (state.fields[field]) {
        el.textContent = state.fields[field];
        el.className = "field-value";
      } else {
        el.textContent = "not set";
        el.className = "field-value empty";
      }
    }

    // Pagination
    const pagVal = shadow.getElementById("rit-val-pagination");
    const clearBtn = shadow.getElementById("rit-clear-pagination");
    const maxRow = shadow.getElementById("rit-max-pages-row");
    if (state.paginationSelector) {
      pagVal.textContent = state.paginationSelector;
      pagVal.className = "field-value";
      clearBtn.style.display = "";
      maxRow.style.display = "";
    } else {
      pagVal.textContent = "not set";
      pagVal.className = "field-value empty";
      clearBtn.style.display = "none";
      maxRow.style.display = "none";
    }

    // Wait-for row
    const jsRender = shadow.getElementById("rit-js-render").checked;
    shadow.getElementById("rit-wait-for-row").style.display = jsRender ? "" : "none";

    // Pick button states
    shadow.querySelectorAll("[data-field]").forEach(btn => {
      const field = btn.dataset.field;
      if (state.pickingField === field) {
        btn.textContent = "cancel";
        btn.className = "field-btn picking";
      } else {
        btn.textContent = "pick";
        btn.className = "field-btn";
      }
    });

    const pickArticleBtn = shadow.getElementById("rit-pick-article");
    if (state.pickingField === "article") {
      pickArticleBtn.textContent = "Cancel";
      pickArticleBtn.className = "field-btn picking";
    } else {
      pickArticleBtn.textContent = "Pick element";
      pickArticleBtn.className = "field-btn";
    }

    // Action buttons
    const ready = !!state.articleSelector && !!state.fields.title;
    shadow.getElementById("rit-btn-preview").disabled = !ready;
    shadow.getElementById("rit-btn-save").disabled = !ready;
    shadow.getElementById("rit-btn-download").disabled = !ready;
  }

  function setStatus(msg, isError = false) {
    const el = shadow.getElementById("rit-status");
    el.textContent = msg;
    el.className = isError ? "status error" : "status";
    if (msg) setTimeout(() => { if (el) el.textContent = ""; }, 3000);
  }

  // ---- Bind panel events ----

  function bindEvents() {
    if (!shadow) return;

    shadow.getElementById("rit-close").addEventListener("click", removePanel);

    shadow.getElementById("rit-pick-article").addEventListener("click", () => {
      if (state.pickingField === "article") stopPicking();
      else startPicking("article");
    });

    shadow.querySelectorAll("[data-field]").forEach(btn => {
      btn.addEventListener("click", () => {
        const field = btn.dataset.field;
        if (state.pickingField === field) stopPicking();
        else startPicking(field);
      });
    });

    shadow.getElementById("rit-clear-pagination").addEventListener("click", () => {
      state.paginationSelector = null;
      updateUI();
    });

    shadow.getElementById("rit-js-render").addEventListener("change", updateUI);

    shadow.getElementById("rit-btn-preview").addEventListener("click", async () => {
      const data = extractPreview();
      const section = shadow.getElementById("rit-preview");
      const countEl = shadow.getElementById("rit-preview-count");
      const itemsEl = shadow.getElementById("rit-preview-items");

      if (!data.items.length) {
        countEl.textContent = "No articles found";
        itemsEl.innerHTML = "";
        section.className = "preview-section visible";
        return;
      }

      countEl.textContent = `Found ${data.items.length} articles`;
      itemsEl.innerHTML = "";

      // Validate selectors against raw HTML
      const issue = await validateAgainstRawHTML();
      if (issue) {
        const warn = document.createElement("div");
        warn.className = "preview-item";
        warn.style.borderLeft = "3px solid #e9a045";
        let html = `<div class="ptitle" style="color:#e9a045">Warning: selector won't work in the app</div>
          <div class="pmeta" style="color:#c0c0c0">${escapeHtml(issue.message)}</div>`;
        if (issue.suggestion) {
          html += `<div class="pmeta" style="color:#00d2ff; margin-top:4px">
            Suggested fix: <strong>${escapeHtml(issue.suggestion)}</strong></div>`;
          html += `<div style="margin-top:4px">
            <button class="field-btn" id="rit-apply-suggestion"
              style="background:#00875a; color:#fff; padding:3px 10px">Apply fix</button></div>`;
        } else {
          html += `<div class="pmeta" style="color:#e9a045; margin-top:4px">
            Enable "JS render" to use Playwright, or manually adjust the selector.</div>`;
        }
        warn.innerHTML = html;
        itemsEl.appendChild(warn);

        // Bind apply button if present
        const applyBtn = itemsEl.querySelector("#rit-apply-suggestion");
        if (applyBtn && issue.suggestion) {
          applyBtn.addEventListener("click", () => {
            state.articleSelector = issue.suggestion;
            updateUI();
            // Re-run preview
            shadow.getElementById("rit-btn-preview").click();
          });
        }
      }

      for (const item of data.items.slice(0, 5)) {
        const div = document.createElement("div");
        div.className = "preview-item";
        div.innerHTML = `
          <div class="ptitle">${escapeHtml(item.title || "(no title)")}</div>
          <div class="pmeta">${escapeHtml(item.url || "")}${item.date ? " \u00b7 " + escapeHtml(item.date) : ""}</div>
        `;
        itemsEl.appendChild(div);
      }
      if (data.items.length > 5) {
        const more = document.createElement("div");
        more.className = "preview-item";
        more.style.color = "#666";
        more.textContent = `...and ${data.items.length - 5} more`;
        itemsEl.appendChild(more);
      }
      section.className = "preview-section visible";
    });

    shadow.getElementById("rit-btn-save").addEventListener("click", () => {
      const config = buildConfig();
      const saveBtn = shadow.getElementById("rit-btn-save");
      saveBtn.disabled = true;
      saveBtn.textContent = "Saving...";

      chrome.runtime.sendMessage(
        { action: "nativeSave", config, category_ids: getSelectedScraperCategoryIds() },
        (response) => {
          saveBtn.disabled = false;
          saveBtn.textContent = "Add to app";

          if (!response || response.nativeNotInstalled) {
            setStatus(
              "Native host not installed. Run: browser_extension/native_host/install.sh",
              true
            );
            return;
          }

          if (response.error) {
            setStatus("Error: " + response.error, true);
            return;
          }

          if (response.success) {
            let msg = "Saved to " + response.path;
            if (response.db_added) {
              msg = "Feed added! Refresh RSS is Terminal to see it.";
            } else if (response.db_note) {
              msg = "Config saved. " + response.db_note;
            }
            setStatus(msg);
          }
        }
      );
    });

    shadow.getElementById("rit-btn-download").addEventListener("click", () => {
      const config = buildConfig();
      const json = JSON.stringify(config, null, 2);
      const blob = new Blob([json], { type: "application/json" });
      const url = URL.createObjectURL(blob);

      const filename = (config.name || "scraper")
        .toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/_+$/, "") + ".json";

      // Create a temporary link and click it to download
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      setStatus("Config downloaded! Use W in RSS is Terminal to add it.");
    });

    shadow.getElementById("rit-btn-reset").addEventListener("click", () => {
      state.articleSelector = null;
      state.fields = {};
      state.paginationSelector = null;
      stopPicking();
      shadow.getElementById("rit-feed-name").value = "";
      shadow.getElementById("rit-js-render").checked = false;
      shadow.getElementById("rit-wait-for").value = "";
      shadow.getElementById("rit-js-hint").classList.remove("visible");
      shadow.getElementById("rit-preview").className = "preview-section";
      updateUI();
    });
  }

  // ---- Message listener ----

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg.action === "togglePanel") {
      togglePanel();
      sendResponse({ ok: true });
    }
    return true;
  });
})();
