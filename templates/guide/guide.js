/* Content guide: section tracking and browser-only comments. */
// When the page has diagrams, start after they are drawn: comments record the
// text of their block, and a diagram's text changes when it is drawn.
(function (start) {
  if (window.guideDiagramsReady) {
    window.guideDiagramsReady.then(start);
  } else {
    start();
  }
})(function () {
  "use strict";

  var data = JSON.parse(document.getElementById("guide-data").textContent);
  var content = document.getElementById("guide-content");
  var sectionLinks = Array.prototype.slice.call(
    document.querySelectorAll(".guide-context .aira-context-nav a"),
  );
  var sections = Array.prototype.slice.call(
    content.querySelectorAll("section.level2"),
  );
  var subnav = document.getElementById("guide-subnav");
  var railTitle = document.getElementById("guide-rail-title");
  var context = document.querySelector(".guide-context");

  // ---- Section and subsection tracking ----

  var currentSection = null;
  var currentSubsection = null;

  function offset() {
    return (context ? context.offsetHeight : 0) + 96;
  }

  function lastAbove(elements) {
    var found = null;
    var limit = offset();
    for (var i = 0; i < elements.length; i++) {
      if (elements[i].getBoundingClientRect().top - limit <= 0) {
        found = elements[i];
      } else {
        break;
      }
    }
    return found || elements[0] || null;
  }

  function headingText(section) {
    var heading = section.querySelector("h2, h3");
    return heading ? heading.textContent : "";
  }

  // With two or more appendices, the header has one "Appendices" link that
  // stands for all of them, and the rail lists them while one is in view.
  var appendices = data.appendices || [];

  function isAppendix(section) {
    return !!section && appendices.some(function (appendix) {
      return appendix.id === section.id;
    });
  }

  // The sections a header link stands for: its target, or, for the
  // Appendices link, every appendix.
  function linkSections(link) {
    var many = link.getAttribute("data-guide-sections");
    if (many) {
      return many.split(/\s+/).filter(Boolean);
    }
    var href = link.getAttribute("href") || "";
    return href.charAt(0) === "#" ? [href.slice(1)] : [];
  }

  function subsectionItems(section, list) {
    var subsections = section
      ? section.querySelectorAll(":scope > section.level3")
      : [];
    Array.prototype.forEach.call(subsections, function (sub) {
      var item = document.createElement("li");
      var link = document.createElement("a");
      link.href = "#" + sub.id;
      link.textContent = headingText(sub);
      item.appendChild(link);
      list.appendChild(item);
    });
    return subsections.length;
  }

  function renderAppendices(section) {
    railTitle.textContent = "Appendices";
    appendices.forEach(function (appendix) {
      var item = document.createElement("li");
      var link = document.createElement("a");
      link.className = "guide-subnav-appendix";
      link.href = "#" + appendix.id;
      link.textContent = appendix.label;
      item.appendChild(link);
      if (appendix.id === section.id) {
        link.setAttribute("aria-current", "page");
        var nested = document.createElement("ul");
        nested.className = "guide-subnav-nested";
        if (subsectionItems(section, nested)) {
          item.appendChild(nested);
        }
      }
      subnav.appendChild(item);
    });
    markFlaggedNav();
  }

  // The front section (Executive Summary, What changed, Scope) has no
  // section-bar entry; while the reader is in it, the rail lists its parts.
  var front = data.front || [];

  function isFront(section) {
    return !!section && front.some(function (part) {
      return part.id === section.id;
    });
  }

  function renderFront(section) {
    railTitle.textContent = "Overview";
    front.forEach(function (part) {
      var item = document.createElement("li");
      var link = document.createElement("a");
      link.className = "guide-subnav-front";
      link.href = "#" + part.id;
      link.textContent = part.label;
      if (part.id === section.id) {
        link.setAttribute("aria-current", "page");
      }
      item.appendChild(link);
      subnav.appendChild(item);
    });
    markFlaggedNav();
  }

  function renderSubnav(section) {
    subnav.textContent = "";
    if (isFront(section)) {
      renderFront(section);
      return;
    }
    if (isAppendix(section)) {
      renderAppendices(section);
      return;
    }
    railTitle.textContent = section ? headingText(section) : "On this page";
    if (!subsectionItems(section, subnav)) {
      var empty = document.createElement("li");
      empty.className = "guide-subnav-empty";
      empty.textContent = "No subsections";
      subnav.appendChild(empty);
      return;
    }
    markFlaggedNav();
  }

  // Mark section and subsection links whose section holds a review flag.
  var flaggedNavTitle = "Has areas flagged for review";
  function markFlaggedNav() {
    sectionLinks
      .concat(Array.prototype.slice.call(subnav.querySelectorAll("a")))
      .forEach(function (link) {
        var flagged = linkSections(link).some(function (id) {
          var target = document.getElementById(id);
          return !!(target && target.querySelector(".guide-review-flagged"));
        });
        link.classList.toggle("guide-nav-flagged", flagged);
        if (flagged) {
          link.title = flaggedNavTitle;
        } else if (link.title === flaggedNavTitle) {
          link.removeAttribute("title");
        }
      });
  }

  // Scroll only the section bar sideways. scrollIntoView would also scroll the
  // window, and because the sticky bar sits inside html's scroll-padding-top,
  // the browser pulls the page back up each time the current section changes.
  function revealInNav(link) {
    var nav = link.parentElement;
    if (!nav || nav.scrollWidth <= nav.clientWidth) {
      return;
    }
    var left = link.offsetLeft - nav.offsetLeft;
    var right = left + link.offsetWidth;
    if (left < nav.scrollLeft || right > nav.scrollLeft + nav.clientWidth) {
      nav.scrollLeft = left - (nav.clientWidth - link.offsetWidth) / 2;
    }
  }

  function update() {
    var section = lastAbove(sections);
    if (section !== currentSection) {
      currentSection = section;
      currentSubsection = null;
      sectionLinks.forEach(function (link) {
        if (section && linkSections(link).indexOf(section.id) !== -1) {
          link.setAttribute("aria-current", "page");
          revealInNav(link);
        } else {
          link.removeAttribute("aria-current");
        }
      });
      renderSubnav(section);
    }
    if (!section) {
      return;
    }
    var subsections = Array.prototype.slice.call(
      section.querySelectorAll(":scope > section.level3"),
    );
    var limit = offset();
    var sub = null;
    subsections.forEach(function (candidate) {
      if (candidate.getBoundingClientRect().top - limit <= 0) {
        sub = candidate;
      }
    });
    if (sub !== currentSubsection) {
      currentSubsection = sub;
      Array.prototype.forEach.call(
        subnav.querySelectorAll("a:not(.guide-subnav-appendix):not(.guide-subnav-front)"),
        function (link) {
          if (sub && link.getAttribute("href") === "#" + sub.id) {
            link.setAttribute("aria-current", "true");
          } else {
            link.removeAttribute("aria-current");
          }
        },
      );
    }
  }

  var pending = false;
  window.addEventListener(
    "scroll",
    function () {
      if (!pending) {
        pending = true;
        window.requestAnimationFrame(function () {
          pending = false;
          update();
        });
      }
    },
    { passive: true },
  );
  window.addEventListener("resize", update);
  update();

  // ---- Shared helpers ----

  function toArray(list) {
    return Array.prototype.slice.call(list);
  }

  function element(tag, className, text) {
    var node = document.createElement(tag);
    if (className) {
      node.className = className;
    }
    if (text !== undefined) {
      node.textContent = text;
    }
    return node;
  }

  function normalizeText(text) {
    return (text || "").replace(/\s+/g, " ").trim();
  }

  // Everything the guide adds inside a block. Snippets and labels leave it out.
  var ADDED_SELECTOR =
    ".guide-comment-button,.guide-flag-button,.guide-flag-marker," +
    ".guide-change-marker,.guide-comment-count,.guide-comment-form,.guide-thread";

  function plainText(node) {
    var copy = node.cloneNode(true);
    toArray(copy.querySelectorAll(ADDED_SELECTOR)).forEach(function (added) {
      added.remove();
    });
    return normalizeText(copy.textContent);
  }

  // Commentable blocks are annotated by the build with their anchor area.
  var BLOCK_SELECTOR = "[data-anchor][data-block-index]";
  var commentBlocks = toArray(content.querySelectorAll(BLOCK_SELECTOR)).filter(
    function (candidate) {
      var parent = candidate.parentElement;
      while (parent && parent !== content) {
        if (parent.matches(BLOCK_SELECTOR)) {
          return false;
        }
        parent = parent.parentElement;
      }
      return true;
    },
  );

  // A table row is a comment block when its table names each row (see
  // "Review anchors"). Its controls go in its last cell; its forms go in a
  // full-width row inserted after it, so the table stays valid.
  function isRowBlock(block) {
    return block.tagName === "TR";
  }

  function controlHost(block) {
    return isRowBlock(block) && block.cells.length
      ? block.cells[block.cells.length - 1]
      : block;
  }

  function rowExtra(row) {
    var next = row.nextElementSibling;
    if (next && next.classList.contains("guide-row-extra")) {
      return next.cells[0];
    }
    var extra = document.createElement("tr");
    extra.className = "guide-row-extra";
    var cell = document.createElement("td");
    cell.colSpan = row.cells.length || 1;
    extra.appendChild(cell);
    row.insertAdjacentElement("afterend", extra);
    return cell;
  }

  // The holder for an inline form under a block.
  function threadAfter(target) {
    var holder;
    if (isRowBlock(target)) {
      var cell = rowExtra(target);
      holder = cell.querySelector(":scope > .guide-thread");
      if (!holder) {
        holder = element("div", "guide-thread");
        cell.insertBefore(holder, cell.firstChild);
      }
      return holder;
    }
    var next = target.nextElementSibling;
    if (next && next.classList.contains("guide-thread")) {
      return next;
    }
    holder = element("div", "guide-thread");
    target.insertAdjacentElement("afterend", holder);
    return holder;
  }

  function formHost(target) {
    return isRowBlock(target) ? rowExtra(target) : target;
  }

  function pruneEmptyHolders() {
    toArray(content.querySelectorAll(".guide-thread")).forEach(function (holder) {
      if (!holder.firstElementChild) {
        holder.remove();
      }
    });
    toArray(content.querySelectorAll(".guide-row-extra")).forEach(function (row) {
      if (!row.cells[0] || !row.cells[0].firstElementChild) {
        row.remove();
      }
    });
  }

  function areaStart(anchor) {
    if (anchor.matches("section")) {
      return (
        anchor.querySelector(
          ":scope > h1, :scope > h2, :scope > h3, :scope > h4, :scope > h5, :scope > h6",
        ) || anchor
      );
    }
    return anchor;
  }

  // The blocks of an anchor's review area, in reading order.
  function areaBlocks(anchorName) {
    return commentBlocks.filter(function (block) {
      return block.dataset.anchor === anchorName;
    });
  }

  // ---- Annotations panel ----
  // One panel with three tabs. The active tab is the lens: it decides which
  // markers the text shows. With the panel closed, the text shows only faint
  // ticks in the margin where something is annotated.

  var LENSES = ["comments", "review", "changes"];

  var annotations = (function () {
    var panel = document.getElementById("guide-annotations");
    var panelBody = document.getElementById("guide-annotations-body");
    var closeButton = document.getElementById("guide-annotations-close");
    var stripButtons = toArray(document.querySelectorAll("[data-guide-lens]"));
    var tabs = toArray(panel.querySelectorAll("[role=tab]"));
    var lists = {
      comments: document.getElementById("guide-list-comments"),
      review: document.getElementById("guide-list-review"),
      changes: document.getElementById("guide-list-changes"),
    };
    var memoryKey = "content-guide-annotations:" + data.id;
    var narrowQuery = window.matchMedia("(max-width: 899.98px)");
    var reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    var state = { open: false, tab: "comments" };
    // The panel's width on wide screens, in pixels. The reading column keeps
    // at least READING_MIN beside it.
    var resizer = document.getElementById("guide-annotations-resize");
    var WIDTH_DEFAULT = 340;
    var WIDTH_MIN = 280;
    var WIDTH_MAX = 640;
    var READING_MIN = 640;
    // Below this much room beside the panel, the right rail goes under the text.
    var RAIL_ROOM = 940;
    var panelWidth = WIDTH_DEFAULT;
    var filters = { commentsAll: false, mine: false, reviewAll: false };
    var filterListeners = [];
    var comments = { placed: [], notPlaced: [], unavailable: false };
    var flags = { placed: [], notPlaced: [] };
    var changes = readChangeMarkers();

    function remembered() {
      try {
        var value = JSON.parse(window.localStorage.getItem(memoryKey) || "null");
        if (value && LENSES.indexOf(value.tab) !== -1) {
          if (typeof value.width === "number") {
            panelWidth = value.width;
          }
          return { open: !!value.open, tab: value.tab };
        }
      } catch (error) {
        /* Storage may be disabled; start closed. */
      }
      return null;
    }

    function remember() {
      try {
        window.localStorage.setItem(
          memoryKey,
          JSON.stringify({ open: state.open, tab: state.tab, width: panelWidth }),
        );
      } catch (error) {
        /* Storage may be disabled; the panel still works for this visit. */
      }
    }

    // ?lens= opens the panel on that tab, over anything remembered.
    var lensParam = null;
    try {
      lensParam = new URL(window.location.href).searchParams.get("lens");
    } catch (error) {
      lensParam = null;
    }
    var saved = remembered();
    if (LENSES.indexOf(lensParam) !== -1) {
      state = { open: true, tab: lensParam };
    } else {
      state = saved || state;
    }

    function stripButton(lens) {
      return stripButtons.filter(function (button) {
        return button.dataset.guideLens === lens;
      })[0];
    }

    function tabButton(lens) {
      return tabs.filter(function (tab) {
        return tab.dataset.guideTab === lens;
      })[0];
    }

    function apply() {
      panel.hidden = !state.open;
      document.body.classList.toggle("guide-panel-open", state.open);
      document.body.classList.toggle("guide-lens-none", !state.open);
      LENSES.forEach(function (lens) {
        document.body.classList.toggle(
          "guide-lens-" + lens,
          state.open && state.tab === lens,
        );
      });
      stripButtons.forEach(function (button) {
        var active = state.open && button.dataset.guideLens === state.tab;
        button.setAttribute("aria-expanded", active ? "true" : "false");
        button.classList.toggle("is-active", active);
      });
      tabs.forEach(function (tab) {
        var selected = tab.dataset.guideTab === state.tab;
        tab.setAttribute("aria-selected", selected ? "true" : "false");
        tab.tabIndex = selected ? 0 : -1;
        document.getElementById(tab.getAttribute("aria-controls")).hidden =
          !selected;
      });
      place();
      fit();
    }

    // ---- Width ----

    function widthLimit() {
      return Math.max(
        WIDTH_MIN,
        Math.min(WIDTH_MAX, window.innerWidth - READING_MIN),
      );
    }

    // Shows the width (kept within the limits for this window) and decides
    // where the right rail goes.
    function fit() {
      var shown = Math.round(
        Math.min(widthLimit(), Math.max(WIDTH_MIN, panelWidth)),
      );
      document.documentElement.style.setProperty(
        "--guide-panel-width",
        shown + "px",
      );
      resizer.setAttribute("aria-valuemin", String(WIDTH_MIN));
      resizer.setAttribute("aria-valuemax", String(widthLimit()));
      resizer.setAttribute("aria-valuenow", String(shown));
      resizer.setAttribute("aria-valuetext", shown + " pixels wide");
      document.body.classList.toggle(
        "guide-rail-below",
        state.open && !narrowQuery.matches && window.innerWidth - shown < RAIL_ROOM,
      );
      return shown;
    }

    function setWidth(width, save) {
      panelWidth = Math.min(widthLimit(), Math.max(WIDTH_MIN, Math.round(width)));
      fit();
      if (save) {
        remember();
      }
    }

    // The panel starts at the window's left edge, so the pointer's x is the width.
    resizer.addEventListener("pointerdown", function (event) {
      if (event.button !== 0) {
        return;
      }
      event.preventDefault();
      resizer.setPointerCapture(event.pointerId);
      document.body.classList.add("guide-resizing");
    });
    resizer.addEventListener("pointermove", function (event) {
      if (resizer.hasPointerCapture(event.pointerId)) {
        setWidth(event.clientX, false);
      }
    });
    function endResize(event) {
      if (resizer.hasPointerCapture(event.pointerId)) {
        resizer.releasePointerCapture(event.pointerId);
      }
      if (document.body.classList.contains("guide-resizing")) {
        document.body.classList.remove("guide-resizing");
        remember();
      }
    }
    resizer.addEventListener("pointerup", endResize);
    resizer.addEventListener("pointercancel", endResize);
    resizer.addEventListener("dblclick", function () {
      setWidth(WIDTH_DEFAULT, true);
    });
    // Arrows resize in steps (larger with Shift); Home resets.
    resizer.addEventListener("keydown", function (event) {
      var step = event.shiftKey ? 64 : 16;
      if (event.key === "ArrowRight") {
        setWidth(fit() + step, true);
      } else if (event.key === "ArrowLeft") {
        setWidth(fit() - step, true);
      } else if (event.key === "Home") {
        setWidth(WIDTH_DEFAULT, true);
      } else {
        return;
      }
      event.preventDefault();
    });

    // On wide screens the panel sits under the sticky section bar.
    function place() {
      var top = context
        ? Math.max(0, context.getBoundingClientRect().bottom)
        : 0;
      panel.style.setProperty("--guide-panel-top", top + "px");
    }

    function open(lens, options) {
      options = options || {};
      state = { open: true, tab: LENSES.indexOf(lens) !== -1 ? lens : state.tab };
      apply();
      remember();
      if (options.focus) {
        tabButton(state.tab).focus();
      }
    }

    function close() {
      state = { open: false, tab: state.tab };
      apply();
      remember();
      stripButton(state.tab).focus();
    }

    stripButtons.forEach(function (button) {
      button.addEventListener("click", function () {
        if (state.open && state.tab === button.dataset.guideLens) {
          close();
        } else {
          open(button.dataset.guideLens, { focus: true });
        }
      });
    });

    tabs.forEach(function (tab, position) {
      tab.addEventListener("click", function () {
        open(tab.dataset.guideTab);
      });
      tab.addEventListener("keydown", function (event) {
        var next = null;
        if (event.key === "ArrowRight") {
          next = tabs[(position + 1) % tabs.length];
        } else if (event.key === "ArrowLeft") {
          next = tabs[(position + tabs.length - 1) % tabs.length];
        } else if (event.key === "Home") {
          next = tabs[0];
        } else if (event.key === "End") {
          next = tabs[tabs.length - 1];
        }
        if (next) {
          event.preventDefault();
          open(next.dataset.guideTab);
          next.focus();
        }
      });
    });

    closeButton.addEventListener("click", close);

    // Esc closes the panel, except while typing, where it belongs to the form.
    document.addEventListener("keydown", function (event) {
      if (event.key !== "Escape" || !state.open || event.defaultPrevented) {
        return;
      }
      var target = event.target;
      if (target && target.closest && target.closest("textarea,input,select")) {
        return;
      }
      close();
    });

    window.addEventListener("scroll", place, { passive: true });
    window.addEventListener("resize", function () {
      place();
      fit();
    });

    // Filters. Each mode tells the panel which ones apply.
    function setPressed(group, value) {
      toArray(group.querySelectorAll("button")).forEach(function (button) {
        button.setAttribute(
          "aria-pressed",
          button.dataset.value === value ? "true" : "false",
        );
      });
    }

    var commentState = panel.querySelector("[data-guide-filter=comments-state]");
    var reviewState = panel.querySelector("[data-guide-filter=review-state]");
    var mineToggle = panel.querySelector("[data-guide-filter=mine]");
    commentState.addEventListener("click", function (event) {
      var button = event.target.closest("button");
      if (!button) {
        return;
      }
      filters.commentsAll = button.dataset.value === "all";
      setPressed(commentState, button.dataset.value);
      filtersChanged();
    });
    reviewState.addEventListener("click", function (event) {
      var button = event.target.closest("button");
      if (!button) {
        return;
      }
      filters.reviewAll = button.dataset.value === "all";
      setPressed(reviewState, button.dataset.value);
      filtersChanged();
    });
    mineToggle.addEventListener("click", function () {
      filters.mine = !filters.mine;
      mineToggle.setAttribute("aria-pressed", filters.mine ? "true" : "false");
      filtersChanged();
    });

    function filtersChanged() {
      renderComments();
      renderReview();
      filterListeners.forEach(function (listener) {
        listener(filters);
      });
    }

    function configure(options) {
      commentState.hidden = !options.commentStates;
      reviewState.parentElement.hidden = !options.flags;
    }

    // Counts appear in the strip and on the tabs. Zero is dimmed; null means
    // the count is not known (for example, before signing in).
    function setCount(lens, value, title) {
      toArray(document.querySelectorAll("[data-guide-count=" + lens + "]")).forEach(
        function (node) {
          node.textContent = value === null ? "–" : String(value);
        },
      );
      [stripButton(lens), tabButton(lens)].forEach(function (button) {
        button.classList.toggle("is-zero", !value);
      });
      var strip = stripButton(lens);
      if (title) {
        strip.title = title;
      } else {
        strip.removeAttribute("title");
      }
    }

    // ---- Lists ----

    function topSection(node) {
      return node && node.closest ? node.closest("section.level2") : null;
    }

    function inOrder(left, right) {
      if (left.target === right.target) {
        return 0;
      }
      return left.target.compareDocumentPosition(right.target) &
        Node.DOCUMENT_POSITION_FOLLOWING
        ? -1
        : 1;
    }

    // A short label for where an item is in the text.
    function describe(target) {
      if (target.matches("section")) {
        return headingText(target);
      }
      if (isRowBlock(target)) {
        return target.cells.length
          ? plainText(target.cells[0]) + " (table row)"
          : "Table row";
      }
      var text = plainText(target);
      if (!text && target.classList.contains("guide-anchor")) {
        var next = target.nextElementSibling;
        text = next ? plainText(next) : "";
      }
      if (!text && target.querySelector("svg")) {
        return "Diagram";
      }
      return text.length > 70 ? text.slice(0, 70) + "…" : text;
    }

    function goTo(target) {
      var focus = target.matches("section") ? areaStart(target) : target;
      focus.scrollIntoView({
        block: narrowQuery.matches ? "start" : "center",
        behavior: reducedMotion.matches ? "auto" : "smooth",
      });
      highlight(focus);
    }

    function highlight(node) {
      node.classList.remove("guide-highlight");
      void node.offsetWidth;
      node.classList.add("guide-highlight");
      window.setTimeout(function () {
        node.classList.remove("guide-highlight");
      }, 2200);
    }

    function whereButton(target) {
      var button = element("button", "guide-where");
      button.type = "button";
      var label = describe(target) || "Show in the text";
      button.appendChild(element("span", "guide-where__arrow", "↳ "));
      button.appendChild(document.createTextNode(label));
      button.title = "Show in the text";
      button.setAttribute("aria-label", "Show in the text: " + label);
      button.addEventListener("click", function () {
        goTo(target);
      });
      return button;
    }

    // Up and Down move between the items of the visible list.
    panel.addEventListener("keydown", function (event) {
      if (
        (event.key !== "ArrowDown" && event.key !== "ArrowUp") ||
        !event.target.classList.contains("guide-where")
      ) {
        return;
      }
      var buttons = toArray(
        lists[state.tab].querySelectorAll(".guide-where"),
      );
      var position = buttons.indexOf(event.target);
      var next = buttons[position + (event.key === "ArrowDown" ? 1 : -1)];
      if (next) {
        event.preventDefault();
        next.focus();
      }
    });

    function renderList(list, placed, notPlaced, emptyText, notPlacedNote) {
      var scroll = panelBody.scrollTop;
      list.textContent = "";
      if (!placed.length && !notPlaced.length) {
        if (emptyText) {
          list.appendChild(element("p", "aira-meta guide-annotation-empty", emptyText));
        }
        return;
      }
      var groups = [];
      placed.slice().sort(inOrder).forEach(function (entry) {
        var section = topSection(entry.target);
        var last = groups[groups.length - 1];
        if (!last || last.section !== section) {
          groups.push({ section: section, entries: [entry] });
        } else {
          last.entries.push(entry);
        }
      });
      groups.forEach(function (group) {
        list.appendChild(
          groupElement(
            group.section ? headingText(group.section) : "Start of document",
            group.section,
            group.entries,
          ),
        );
      });
      if (notPlaced.length) {
        var unplaced = groupElement("Not placed", null, notPlaced);
        unplaced.classList.add("guide-annotation-group--unplaced");
        unplaced.insertBefore(
          element("p", "aira-meta", notPlacedNote),
          unplaced.querySelector("ul"),
        );
        list.appendChild(unplaced);
      }
      panelBody.scrollTop = scroll;
    }

    function groupElement(title, section, entries) {
      var group = element("section", "guide-annotation-group");
      var heading = element("h3", "guide-annotation-group__title");
      if (section) {
        var link = element("a", "", title);
        link.href = "#" + section.id;
        heading.appendChild(link);
      } else {
        heading.appendChild(document.createTextNode(title));
      }
      heading.appendChild(
        element("span", "guide-annotation-group__count", String(entries.length)),
      );
      group.appendChild(heading);
      var items = element("ul", "guide-annotation-items");
      entries.forEach(function (entry) {
        var item = element("li", "guide-annotation-item");
        if (entry.target) {
          item.appendChild(whereButton(entry.target));
        }
        item.appendChild(entry.element);
        items.appendChild(item);
      });
      group.appendChild(items);
      return group;
    }

    // ---- Comments ----

    function visibleComments(entries) {
      return entries.filter(function (entry) {
        return (
          (filters.commentsAll || entry.open !== false) &&
          (!filters.mine || entry.mine)
        );
      });
    }

    function setComments(placed, notPlaced) {
      comments = { placed: placed, notPlaced: notPlaced, unavailable: false };
      renderComments();
    }

    function setCommentsUnavailable(title) {
      comments = { placed: [], notPlaced: [], unavailable: true, title: title };
      renderComments();
    }

    // A line at the top of the Comments tab, such as the version's comment
    // mode. Empty text hides it.
    var labelNote = document.getElementById("guide-label-note");
    function setCommentsNote(text) {
      labelNote.textContent = text || "";
      labelNote.hidden = !text;
    }

    function renderComments() {
      var placed = visibleComments(comments.placed);
      var notPlaced = visibleComments(comments.notPlaced);
      var filtered = filters.mine || filters.commentsAll;
      renderList(
        lists.comments,
        placed,
        notPlaced,
        comments.unavailable
          ? ""
          : filtered
            ? "No comments match these filters."
            : "No comments yet. Point at a paragraph and choose \u{1F4AC} to add one.",
        "These comments' places in the text were not found. An author can re-attach them.",
      );
      // Signed out, the sign-in prompt stands alone.
      commentState.parentElement.hidden = comments.unavailable;
      var openCount = comments.placed
        .concat(comments.notPlaced)
        .filter(function (entry) {
          return entry.open !== false && entry.counted !== false;
        }).length;
      setCount(
        "comments",
        comments.unavailable ? null : openCount,
        comments.unavailable ? comments.title : "",
      );
      renderCommentCounts(placed);
      refreshTicks();
    }

    // In the Comments lens, each block with comments shows how many. The
    // count opens the panel at its first thread.
    function renderCommentCounts(entries) {
      toArray(content.querySelectorAll(".guide-comment-count")).forEach(
        function (node) {
          node.remove();
        },
      );
      toArray(content.querySelectorAll(".guide-has-comments")).forEach(
        function (node) {
          node.classList.remove("guide-has-comments");
        },
      );
      var byTarget = [];
      entries.forEach(function (entry) {
        var found = byTarget.filter(function (group) {
          return group.target === entry.target;
        })[0];
        if (found) {
          found.entries.push(entry);
        } else {
          byTarget.push({ target: entry.target, entries: [entry] });
        }
      });
      byTarget.forEach(function (group) {
        var target = group.target;
        var row = isRowBlock(target);
        var count = element(
          "button",
          "guide-comment-count" + (row ? " guide-comment-count--row" : ""),
        );
        count.type = "button";
        count.appendChild(element("span", "", "\u{1F4AC}")).setAttribute(
          "aria-hidden",
          "true",
        );
        count.appendChild(document.createTextNode(" " + group.entries.length));
        var noun = group.entries.length === 1 ? "comment" : "comments";
        count.setAttribute(
          "aria-label",
          group.entries.length + " " + noun + "; show in the panel",
        );
        count.title = "Show " + noun + " in the panel";
        count.addEventListener("click", function () {
          reveal("comments", group.entries[0].element);
        });
        var host = target.matches("section") ? areaStart(target) : target;
        host.classList.add("guide-has-comments");
        if (row && target.cells.length) {
          target.cells[0].insertBefore(count, target.cells[0].firstChild);
        } else {
          (row ? target : host).appendChild(count);
        }
      });
    }

    // Open the panel on a tab and bring one of its items into view.
    function reveal(lens, node) {
      open(lens);
      if (!node) {
        return;
      }
      var item = node.closest(".guide-annotation-item") || node;
      item.scrollIntoView({ block: "nearest" });
      highlight(item);
    }

    // ---- Review flags and change markers ----

    function setFlags(placed, notPlaced) {
      flags = { placed: placed, notPlaced: notPlaced };
      renderReview();
    }

    function visibleFlags(entries) {
      return entries.filter(function (entry) {
        return filters.reviewAll || entry.open !== false;
      });
    }

    function renderReview() {
      var feedback = changes.filter(function (change) {
        return change.marker.level === "feedback";
      });
      var placed = visibleFlags(flags.placed).concat(
        feedback.filter(function (change) {
          return change.target;
        }).map(function (change) {
          return { target: change.target, element: changeCard(change) };
        }),
      );
      var notPlaced = visibleFlags(flags.notPlaced).concat(
        feedback.filter(function (change) {
          return !change.target;
        }).map(function (change) {
          return { target: null, element: changeCard(change) };
        }),
      );
      renderList(
        lists.review,
        placed,
        notPlaced,
        filters.reviewAll
          ? "Nothing has been flagged for review."
          : "Nothing is flagged for review.",
        "These areas are no longer in the text.",
      );
      var openFlags = flags.placed.concat(flags.notPlaced).filter(function (entry) {
        return entry.open !== false && entry.counted !== false;
      }).length;
      setCount("review", openFlags + feedback.length);
      refreshTicks();
    }

    // The change-marker contract: the build emits a JSON script element with
    // the ID guide-change-markers, holding a list of
    // {anchor, blockIndex?, version, level, note}. See the README.
    function readChangeMarkers() {
      var node = document.getElementById("guide-change-markers");
      if (!node) {
        return [];
      }
      var list;
      try {
        list = JSON.parse(node.textContent);
      } catch (error) {
        window.console.warn("guide-change-markers is not valid JSON.");
        return [];
      }
      if (!Array.isArray(list)) {
        return [];
      }
      return list
        .filter(function (marker) {
          var valid =
            marker &&
            typeof marker.anchor === "string" &&
            typeof marker.version === "string" &&
            (marker.level === "changed" || marker.level === "feedback") &&
            typeof marker.note === "string" &&
            normalizeText(marker.note) &&
            (marker.blockIndex === undefined ||
              marker.blockIndex === null ||
              typeof marker.blockIndex === "number");
          if (!valid) {
            window.console.warn("Ignoring a malformed change marker.", marker);
          }
          return valid;
        })
        .map(placeChange);
    }

    // Where a change marker goes. A section anchor covers the whole section;
    // a row anchor covers its row; any other anchor covers its area's blocks,
    // or one of them when blockIndex is given.
    function placeChange(marker) {
      var change = { marker: marker, target: null, covered: [], kind: null };
      var anchor = document.getElementById(marker.anchor);
      if (!anchor) {
        return change;
      }
      if (anchor.matches("section")) {
        change.kind = "section";
        change.target = anchor;
        change.covered = [anchor];
      } else if (isRowBlock(anchor)) {
        change.kind = "row";
        change.target = anchor;
        change.covered = [anchor];
      } else {
        var covered = areaBlocks(marker.anchor).filter(function (block) {
          return (
            marker.blockIndex === undefined ||
            marker.blockIndex === null ||
            Number(block.dataset.blockIndex) === marker.blockIndex
          );
        });
        if (!covered.length) {
          return change;
        }
        change.kind = "blocks";
        change.target = covered[0];
        change.covered = covered;
      }
      drawChange(change);
      return change;
    }

    function changeLabel(marker) {
      return marker.level === "feedback"
        ? "Changed · feedback wanted"
        : "Changed in " + marker.version;
    }

    function drawChange(change) {
      var marker = change.marker;
      var feedback = marker.level === "feedback";
      var row = change.kind === "row";
      var holder = element(
        row ? "span" : "div",
        "guide-change-marker" +
          (feedback ? " guide-change-marker--feedback" : "") +
          (row ? " guide-change-marker--row" : ""),
      );
      var badge = element("button", "guide-change-badge");
      badge.type = "button";
      badge.setAttribute("aria-expanded", "false");
      badge.appendChild(element("span", "", feedback ? "⚑" : "Δ"))
        .setAttribute("aria-hidden", "true");
      badge.appendChild(
        element(
          "span",
          row ? "aira-visually-hidden" : "guide-change-badge__label",
          changeLabel(marker),
        ),
      );
      holder.appendChild(badge);
      var popover = element("div", "guide-change-popover");
      popover.setAttribute("role", "group");
      popover.setAttribute("aria-label", changeLabel(marker));
      popover.appendChild(
        element(
          "p",
          "guide-change-popover__title",
          "Changed in " + marker.version + (feedback ? " · feedback wanted" : ""),
        ),
      );
      popover.appendChild(element("p", "guide-change-popover__note", marker.note));
      holder.appendChild(popover);
      function setOpen(isOpen) {
        holder.classList.toggle("is-open", isOpen);
        badge.setAttribute("aria-expanded", isOpen ? "true" : "false");
      }
      badge.addEventListener("click", function () {
        setOpen(!holder.classList.contains("is-open"));
      });
      holder.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && holder.classList.contains("is-open")) {
          event.preventDefault();
          setOpen(false);
          badge.focus();
        }
      });

      var classes = ["guide-changed"].concat(
        feedback ? ["guide-changed--feedback"] : [],
      );
      if (change.kind === "section") {
        areaStart(change.target).insertAdjacentElement("afterend", holder);
        change.target.classList.add.apply(change.target.classList, classes);
      } else if (row) {
        var cell = change.target.cells[0];
        if (cell) {
          cell.insertBefore(holder, cell.firstChild);
        }
        change.target.classList.add.apply(change.target.classList, classes);
      } else {
        change.target.parentNode.insertBefore(holder, change.target);
        change.covered.forEach(function (block) {
          block.classList.add.apply(block.classList, classes);
          var previous = block.previousElementSibling;
          if (
            previous &&
            (previous === holder || previous.classList.contains("guide-changed"))
          ) {
            block.classList.add("guide-changed--continued");
          }
        });
      }
    }

    function changeCard(change) {
      var marker = change.marker;
      var feedback = marker.level === "feedback";
      var card = element(
        "article",
        "guide-change-card" + (feedback ? " guide-change-card--feedback" : ""),
      );
      var label = element("p", "guide-card-label");
      label.appendChild(element("span", "", feedback ? "⚑ " : "Δ "))
        .setAttribute("aria-hidden", "true");
      label.appendChild(
        document.createTextNode(
          feedback ? "Changed · feedback wanted" : "Changed",
        ),
      );
      label.appendChild(element("span", "guide-card-version", marker.version));
      card.appendChild(label);
      card.appendChild(element("p", "guide-card-note", marker.note));
      return card;
    }

    function renderChanges() {
      var placed = changes.filter(function (change) {
        return change.target;
      }).map(function (change) {
        return { target: change.target, element: changeCard(change) };
      });
      var notPlaced = changes.filter(function (change) {
        return !change.target;
      }).map(function (change) {
        return { target: null, element: changeCard(change) };
      });
      renderList(
        lists.changes,
        placed,
        notPlaced,
        "No changes are marked in this version.",
        "These markers name an area that is not in the text.",
      );
      setCount("changes", changes.length);
    }

    // ---- Margin ticks (panel closed) ----

    function tickElements(entry) {
      if (entry.ticks) {
        return entry.ticks;
      }
      return entry.target ? [entry.target.matches("section") ? areaStart(entry.target) : entry.target] : [];
    }

    function refreshTicks() {
      toArray(content.querySelectorAll(".guide-annotated")).forEach(function (node) {
        node.classList.remove("guide-annotated");
      });
      var entries = comments.placed
        .filter(function (entry) {
          return entry.open !== false;
        })
        .concat(
          flags.placed.filter(function (entry) {
            return entry.open !== false;
          }),
        );
      changes.forEach(function (change) {
        if (change.target) {
          entries.push({
            target: change.target,
            ticks:
              change.kind === "section"
                ? [areaStart(change.target)]
                : change.covered,
          });
        }
      });
      entries.forEach(function (entry) {
        tickElements(entry).forEach(function (node) {
          node.classList.add("guide-annotated");
        });
      });
    }

    renderChanges();
    renderReview();
    renderComments();
    apply();

    return {
      configure: configure,
      setComments: setComments,
      setCommentsUnavailable: setCommentsUnavailable,
      setCommentsNote: setCommentsNote,
      setFlags: setFlags,
      onFilter: function (listener) {
        filterListeners.push(listener);
      },
      filters: function () {
        return filters;
      },
      open: open,
      reveal: reveal,
    };
  })();

  // ---- Comments ----

  if (data.comments && data.comments.mode === "interophub") {
    startInteropHubComments();
    return;
  }

  var STORAGE_KEY = "content-guide-comments:" + data.id;
  var NAME_KEY = "content-guide-commenter";
  var FORMAT = "content-guide-comments";
  var memory = {};

  function load(key) {
    try {
      var value = window.localStorage.getItem(key);
      return value === null ? memory[key] || null : value;
    } catch (error) {
      return memory[key] || null;
    }
  }

  function store(key, value) {
    memory[key] = value;
    try {
      window.localStorage.setItem(key, value);
    } catch (error) {
      /* Memory only: comments last until the page is closed. */
    }
  }

  var comments = [];
  var localSubscribers = [];
  var localStore = {
    load: function () {
      try {
        return JSON.parse(load(STORAGE_KEY) || "[]");
      } catch (error) {
        return [];
      }
    },
    add: function (comment) {
      comments.push(comment);
      localStore.persist();
      return comment;
    },
    reply: function (comment) {
      return localStore.add(comment);
    },
    edit: function (comment, text) {
      comment.text = text;
      comment.updated = new Date().toISOString();
      localStore.persist();
      return comment;
    },
    withdraw: function (comment) {
      comments = comments.filter(function (other) {
        return other.id !== comment.id;
      });
      localStore.persist();
    },
    subscribe: function (listener) {
      localSubscribers.push(listener);
      return function () {
        localSubscribers = localSubscribers.filter(function (item) {
          return item !== listener;
        });
      };
    },
    persist: function () {
      store(STORAGE_KEY, JSON.stringify(comments));
      localSubscribers.forEach(function (listener) {
        listener(comments);
      });
    },
  };
  comments = localStore.load();

  // Local mode: no comment states and no review flags. The Review tab shows
  // only the source's feedback-wanted change markers.
  annotations.configure({ commentStates: false, flags: false });
  var nameInput = document.getElementById("guide-commenter");
  nameInput.value = load(NAME_KEY) || "";
  nameInput.addEventListener("change", function () {
    store(NAME_KEY, nameInput.value.trim());
    render();
  });

  function save() {
    localStore.persist();
  }

  var normalize = normalizeText;

  function blockSnippet(block) {
    return plainText(block).slice(0, 120);
  }

  function newId() {
    if (window.crypto && window.crypto.randomUUID) {
      return window.crypto.randomUUID();
    }
    return (
      "c-" +
      Date.now().toString(36) +
      "-" +
      Math.random().toString(36).slice(2, 10)
    );
  }

  var blocks = commentBlocks;

  blocks.forEach(function (block) {
    var section = block.closest("section");
    block.dataset.guideSection = section ? section.id : "top";
    block.dataset.guideText = blockSnippet(block);
    block.classList.add("guide-block");

    var button = document.createElement("button");
    button.type = "button";
    button.className = "guide-comment-button";
    button.title = "Comment on this";
    button.setAttribute("aria-label", "Comment on this paragraph");
    button.textContent = "\u{1F4AC}";
    button.addEventListener("mousedown", function (event) {
      event.preventDefault();
    });
    button.addEventListener("click", function () {
      openForm(block, selectionWithin(block));
    });
    controlHost(block).appendChild(button);
  });

  function selectionWithin(block) {
    var selection = window.getSelection();
    if (!selection || selection.isCollapsed || !selection.rangeCount) {
      return "";
    }
    var range = selection.getRangeAt(0);
    if (!block.contains(range.commonAncestorContainer)) {
      return "";
    }
    return normalize(selection.toString()).slice(0, 500);
  }

  function legacyBlock(comment) {
    var exact = blocks.filter(function (block) {
      return (
        block.dataset.guideSection === comment.sectionId &&
        Number(block.dataset.blockIndex) + 1 === Number(comment.blockIndex)
      );
    })[0];
    var snippet = normalize(comment.blockText).slice(0, 60);
    if (exact && exact.dataset.guideText.slice(0, 60) === snippet) {
      return exact;
    }
    var moved = blocks.filter(function (block) {
      return snippet && block.dataset.guideText.indexOf(snippet) === 0;
    })[0];
    if (moved) {
      return moved;
    }
    if (comment.quote) {
      var quoted = blocks.filter(function (block) {
        return plainText(block).indexOf(comment.quote) !== -1;
      })[0];
      if (quoted) {
        return quoted;
      }
    }
    return null;
  }

  function snippetSimilarity(left, right) {
    left = normalize(left).toLowerCase();
    right = normalize(right).toLowerCase();
    if (left === right) {
      return 1;
    }
    if (!left || !right) {
      return 0;
    }
    var leftWords = left.split(/\s+/);
    var rightWords = right.split(/\s+/);
    var seen = {};
    var shared = 0;
    leftWords.forEach(function (word) {
      seen[word] = true;
    });
    rightWords.forEach(function (word) {
      if (seen[word]) {
        shared += 1;
        delete seen[word];
      }
    });
    return shared / Math.max(leftWords.length, rightWords.length);
  }

  function placement(comment) {
    if (!comment.anchor) {
      var legacy = legacyBlock(comment);
      return legacy ? { block: legacy, target: legacy } : null;
    }
    var anchor = document.getElementById(comment.anchor);
    if (!anchor) {
      return null;
    }
    var matches = areaBlocks(comment.anchor).filter(function (block) {
      return snippetSimilarity(blockSnippet(block), comment.snippet) >= 0.75;
    });
    var preferred = matches.filter(function (block) {
      return block.dataset.blockIndex === String(comment.blockIndex);
    })[0];
    var block = preferred || matches[0] || null;
    return { block: block, target: block || areaStart(anchor) };
  }

  function formatTime(iso) {
    try {
      return new Date(iso).toLocaleString([], {
        dateStyle: "medium",
        timeStyle: "short",
      });
    } catch (error) {
      return iso;
    }
  }

  function commentElement(comment) {
    var item = document.createElement("div");
    item.className = "guide-comment";
    item.id = "comment-" + comment.id;

    var meta = document.createElement("div");
    meta.className = "guide-comment__meta";
    var author = document.createElement("span");
    author.className = "guide-comment__author";
    author.textContent = comment.author || "Anonymous";
    var when = document.createElement("span");
    when.textContent =
      formatTime(comment.created) +
      (comment.documentVersion && comment.documentVersion !== data.version
        ? " · on " + comment.documentVersion
        : "");
    var tools = document.createElement("span");
    tools.className = "guide-comment__tools";
    var edit = document.createElement("button");
    edit.type = "button";
    edit.textContent = "Edit";
    edit.addEventListener("click", function () {
      var placed = placement(comment);
      openForm(placed && placed.block, comment.quote, comment, item);
    });
    var remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "Delete";
    remove.addEventListener("click", function () {
      localStore.withdraw(comment);
      render();
    });
    tools.appendChild(edit);
    tools.appendChild(remove);
    meta.appendChild(author);
    meta.appendChild(when);
    meta.appendChild(tools);
    item.appendChild(meta);

    if (comment.quote) {
      var quote = document.createElement("p");
      quote.className = "guide-comment__quote";
      quote.textContent = "“" + comment.quote + "”";
      item.appendChild(quote);
    }
    var text = document.createElement("p");
    text.className = "guide-comment__text";
    text.textContent = comment.text;
    item.appendChild(text);
    return item;
  }

  function isMine(comment) {
    var me = nameInput.value.trim();
    return !!me && normalize(comment.author) === normalize(me);
  }

  // Threads are listed in the panel; the text keeps only inline forms.
  function render() {
    pruneEmptyHolders();
    comments.sort(function (a, b) {
      return (a.created || "").localeCompare(b.created || "");
    });
    var placed = [];
    var unplaced = [];
    comments.forEach(function (comment) {
      var where = placement(comment);
      var entry = {
        element: commentElement(comment),
        target: where ? where.target : null,
        open: true,
        mine: isMine(comment),
      };
      (where ? placed : unplaced).push(entry);
    });
    annotations.setComments(placed, unplaced);
    followHash();
  }

  function closeForms() {
    toArray(document.querySelectorAll(".guide-comment-form")).forEach(
      function (form) {
        form.remove();
      },
    );
    pruneEmptyHolders();
  }

  function sectionTitle(block) {
    var section = block.closest("section");
    return section ? headingText(section) : "";
  }

  // A new comment's form opens under its block; an edit opens in the panel.
  function openForm(block, quote, existing, host) {
    closeForms();
    var form = document.createElement("form");
    form.className = "guide-comment-form";

    if (quote) {
      var quoteText = document.createElement("p");
      quoteText.className = "guide-comment__quote";
      quoteText.textContent = "“" + quote + "”";
      form.appendChild(quoteText);
    }
    var textarea = document.createElement("textarea");
    textarea.className = "aira-textarea";
    textarea.required = true;
    textarea.placeholder = "Add a comment (Ctrl+Enter to save, Esc to cancel)";
    textarea.setAttribute("aria-label", "Comment");
    textarea.value = existing ? existing.text : "";
    form.appendChild(textarea);

    var actions = document.createElement("div");
    actions.className = "guide-comment-actions";
    var submit = document.createElement("button");
    submit.type = "submit";
    submit.className = "aira-button aira-button--primary aira-button--small";
    submit.textContent = existing ? "Save" : "Add comment";
    var cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "aira-button aira-button--ghost aira-button--small";
    cancel.textContent = "Cancel";
    cancel.addEventListener("click", closeForms);
    actions.appendChild(submit);
    actions.appendChild(cancel);
    form.appendChild(actions);

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var text = textarea.value.trim();
      if (!text) {
        return;
      }
      var author = nameInput.value.trim();
      store(NAME_KEY, author);
      var id = existing ? existing.id : newId();
      if (existing) {
        localStore.edit(existing, text);
      } else {
        localStore.add({
          id: id,
          documentId: data.id,
          documentVersion: data.version,
          sectionId: block.dataset.guideSection,
          sectionTitle: sectionTitle(block),
          anchor: block.dataset.anchor,
          blockIndex: Number(block.dataset.blockIndex),
          snippet: blockSnippet(block),
          blockText: block.dataset.guideText,
          quote: quote || "",
          author: author,
          created: new Date().toISOString(),
          text: text,
        });
      }
      closeForms();
      render();
      annotations.reveal("comments", document.getElementById("comment-" + id));
    });
    form.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        event.preventDefault();
        closeForms();
      } else if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
        form.requestSubmit();
      }
    });

    (host || threadAfter(block)).appendChild(form);
    textarea.focus();
    if (!nameInput.value.trim()) {
      annotations.open("comments");
      nameInput.classList.add("guide-flash");
    }
  }

  document
    .getElementById("guide-comments-download")
    .addEventListener("click", function () {
      var author = nameInput.value.trim() || "comments";
      var payload = {
        format: FORMAT,
        formatVersion: 1,
        documentId: data.id,
        documentTitle: data.title,
        documentVersion: data.version,
        exported: new Date().toISOString(),
        exportedBy: nameInput.value.trim(),
        comments: comments,
      };
      var blob = new Blob([JSON.stringify(payload, null, 2)], {
        type: "application/json",
      });
      var link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download =
        data.id +
        "-comments-" +
        author.toLowerCase().replace(/[^a-z0-9]+/g, "-") +
        "-" +
        new Date().toISOString().slice(0, 10) +
        ".json";
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(function () {
        URL.revokeObjectURL(link.href);
      }, 1000);
    });

  document
    .getElementById("guide-comments-load")
    .addEventListener("change", function (event) {
      var files = Array.prototype.slice.call(event.target.files || []);
      var known = {};
      comments.forEach(function (comment) {
        known[comment.id] = comment;
      });
      var remaining = files.length;
      files.forEach(function (file) {
        var reader = new FileReader();
        reader.onload = function () {
          try {
            var payload = JSON.parse(reader.result);
            if (payload.format === FORMAT && Array.isArray(payload.comments)) {
              payload.comments.forEach(function (comment) {
                if (comment && comment.id && comment.text) {
                  known[comment.id] = comment;
                }
              });
            }
          } catch (error) {
            /* Ignore files that are not comment exports. */
          }
          remaining -= 1;
          if (remaining === 0) {
            comments = Object.keys(known).map(function (key) {
              return known[key];
            });
            save();
            render();
          }
        };
        reader.readAsText(file);
      });
      event.target.value = "";
    });

  document
    .getElementById("guide-comments-clear")
    .addEventListener("click", function () {
      var control = this;
      var holder = control.parentElement;
      if (
        !comments.length ||
        (holder.nextElementSibling &&
          holder.nextElementSibling.classList.contains("guide-confirmation"))
      ) {
        return;
      }
      var prompt = document.createElement("div");
      prompt.className = "guide-confirmation";
      prompt.textContent =
        "Remove all " +
        comments.length +
        " comments from this browser? Download them first if you need them. ";
      var remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "Clear all";
      remove.addEventListener("click", function () {
        comments = [];
        save();
        render();
        prompt.remove();
      });
      prompt.appendChild(remove);
      var cancel = document.createElement("button");
      cancel.type = "button";
      cancel.textContent = "Cancel";
      cancel.addEventListener("click", function () {
        prompt.remove();
      });
      prompt.appendChild(cancel);
      holder.insertAdjacentElement("afterend", prompt);
    });

  function followHash() {
    toArray(document.querySelectorAll(".guide-comment--target")).forEach(
      function (item) {
        item.classList.remove("guide-comment--target");
      },
    );
    var match = window.location.hash.match(/^#comment-(.+)$/);
    if (!match) {
      return;
    }
    var comment = document.getElementById("comment-" + match[1]);
    if (!comment) {
      return;
    }
    comment.classList.add("guide-comment--target");
    annotations.reveal("comments", comment);
  }

  window.addEventListener("hashchange", followHash);

  render();

  /* Remote comments use the same placement model but keep all persistence and
     change notifications behind this store-shaped client. */
  function startInteropHubComments() {
    var settings = data.comments;
    var hub = settings.hub;
    var documentKey = settings.document;
    var tokenKey = "content-guide-token:" + hub + ":" + documentKey;
    var authKey = "content-guide-signin:" + hub + ":" + documentKey;
    var noticePrefix = "content-guide-comment-notice:" + hub + ":";
    var draftPrefix = "content-guide-draft:" + hub + ":" + documentKey + ":";
    var status = document.getElementById("guide-comments-status");
    var remoteBlocks = commentBlocks;
    var threads = [];
    var reviewFlags = [];
    var clearedFlags = [];
    var openFlagAnchor = null;
    var showClosed = false;
    var showCleared = false;
    // This page's label settings from InteropHub (contract 5.3.1): undefined
    // until a read answers, null when the hub does not know this address.
    var labelPolicy;
    var documentInfo = null;
    var serverTime = null;
    var pollTimer = null;
    var pollStep = 0;
    var pollDelays = [30000, 60000, 600000, 1800000];
    var auth = readJson(window.localStorage, tokenKey);

    toArray(document.querySelectorAll(".guide-local-control")).forEach(
      function (item) {
        item.hidden = true;
      },
    );
    annotations.configure({ commentStates: true, flags: true });
    annotations.onFilter(function (filters) {
      if (filters.commentsAll !== showClosed) {
        showClosed = filters.commentsAll;
        if (validAuth()) {
          // Keep any form opened while the list reloads.
          store
            .load()
            .then(function () {
              renderRemote(true);
              restartPolling();
            })
            .catch(showStatusError);
        }
      }
      if (filters.reviewAll !== showCleared) {
        showCleared = filters.reviewAll;
        loadClearedFlags()
          .then(function () {
            renderRemote(true);
          })
          .catch(showStatusError);
      }
    });

    function normalizeRemote(value) {
      return (value || "").replace(/\s+/g, " ").trim();
    }

    function readJson(storage, key) {
      try {
        return JSON.parse(storage.getItem(key) || "null");
      } catch (error) {
        return null;
      }
    }

    function writeJson(storage, key, value) {
      try {
        if (value === null) {
          storage.removeItem(key);
        } else {
          storage.setItem(key, JSON.stringify(value));
        }
      } catch (error) {
        /* Storage may be disabled; the page still works for this visit. */
      }
    }

    function validAuth() {
      if (auth && auth.accessToken && Date.parse(auth.expiresAt) > Date.now()) {
        return auth;
      }
      auth = null;
      writeJson(window.localStorage, tokenKey, null);
      return null;
    }

    function errorMessage(error) {
      return error && error.message
        ? error.message
        : "The comment service could not complete the request.";
    }

    function request(path, options) {
      options = options || {};
      var headers = { "Content-Type": "application/json" };
      if (options.token !== false && validAuth()) {
        headers.Authorization = "Bearer " + auth.accessToken;
      }
      return window
        .fetch(hub + path, {
          method: options.method || "GET",
          headers: headers,
          body:
            options.body === undefined
              ? undefined
              : JSON.stringify(options.body),
        })
        .then(function (response) {
          if (response.status === 401) {
            auth = null;
            writeJson(window.localStorage, tokenKey, null);
            stopPolling();
            threads = [];
            renderRemote();
            renderIdentity();
            throw { handled: true, message: "Sign in to comment" };
          }
          if (response.status === 204) {
            return null;
          }
          return response
            .json()
            .then(
              function (body) {
                return { body: body, fromHub: true };
              },
              function () {
                return { body: {}, fromHub: false };
              },
            )
            .then(function (result) {
              var body = result.body || {};
              if (!response.ok) {
                throw {
                  status: response.status,
                  blocked: !result.fromHub || !body.message,
                  message:
                    result.fromHub && body.message
                      ? body.message
                      : blockedMessage(response.status),
                  body: body,
                };
              }
              return body;
            });
        }, function () {
          throw {
            network: true,
            message:
              "Could not reach InteropHub (network error at " +
              utcStamp() +
              "). Check your connection and try again.",
          };
        });
    }

    // A failed response that is not InteropHub's JSON came from something in
    // between, such as a proxy or web application firewall. Say so, with the
    // status and time, so a report can be matched to that system's logs.
    function blockedMessage(status) {
      return (
        "This request was stopped before it reached InteropHub (HTTP " +
        status +
        " at " +
        utcStamp() +
        "). Please report this with the time shown."
      );
    }

    function utcStamp() {
      return new Date().toISOString().slice(0, 19).replace("T", " ") + " UTC";
    }

    function draftStorageKey(draft) {
      if (!draft || !auth || !auth.user) {
        return null;
      }
      return draftPrefix + auth.user.userId + ":" + draft;
    }

    function readDraft(draft) {
      var key = draftStorageKey(draft);
      if (!key) {
        return null;
      }
      try {
        return window.localStorage.getItem(key);
      } catch (error) {
        return null;
      }
    }

    function writeDraft(draft, value) {
      var key = draftStorageKey(draft);
      if (!key) {
        return;
      }
      try {
        if (value) {
          window.localStorage.setItem(key, value);
        } else {
          window.localStorage.removeItem(key);
        }
      } catch (error) {
        /* Storage may be disabled; the open form still keeps the text. */
      }
    }

    // The page's address, which InteropHub resolves to its label (contract
    // 5.4.1). Longer than the hub accepts: not sent, and the page is treated
    // as having no label.
    function pageUrl() {
      var href = window.location.href;
      return href.length <= 2000 ? href : undefined;
    }

    function commentsQuery(extra) {
      var parts = extra ? [extra] : [];
      if (pageUrl()) {
        parts.push("pageUrl=" + encodeURIComponent(pageUrl()));
      }
      return parts.length ? "?" + parts.join("&") : "";
    }

    // Returns true when the comment mode changed since the last answer.
    function acceptPolicy(result) {
      var before = labelPolicy === undefined ? undefined : labelPolicy && labelPolicy.commentMode;
      labelPolicy = "labelPolicy" in result ? result.labelPolicy : null;
      applyPolicy();
      return before !== undefined && before !== (labelPolicy && labelPolicy.commentMode);
    }

    function isClosed() {
      return !!(labelPolicy && labelPolicy.commentMode === "closed");
    }

    function isRelease() {
      return !!(labelPolicy && labelPolicy.commentMode === "release");
    }

    // Closed: no comments, and no comment or flag controls. Release: say what
    // the tab shows. A page with no label behaves as before.
    function applyPolicy() {
      document.body.classList.toggle("guide-comments-closed", isClosed());
      if (isClosed()) {
        annotations.setCommentsNote("Comments are closed on this version.");
      } else if (isRelease()) {
        annotations.setCommentsNote(
          "This tab shows comments for this release and earlier." +
            (isAuthor() ? " Comments from other versions are marked." : ""),
        );
      } else {
        annotations.setCommentsNote("");
      }
    }

    var store = {
      load: function () {
        return request("/api/guide/" + encodeURIComponent(documentKey)).then(
          function (info) {
            documentInfo = info;
            serverTime = info.serverTime;
            if (!info.permissions.canView) {
              threads = [];
              return null;
            }
            return request(
              "/api/guide/" +
                encodeURIComponent(documentKey) +
                "/comments" +
                commentsQuery(showClosed ? "state=all" : ""),
            ).then(function (result) {
              threads = result.comments || [];
              reviewFlags = result.reviewFlags || [];
              serverTime = result.serverTime;
              acceptPolicy(result);
            });
          },
        );
      },
      clearedFlags: function () {
        return request(
          "/api/guide/" +
            encodeURIComponent(documentKey) +
            "/review-flags?includeCleared=true",
        );
      },
      add: function (block, text) {
        return request(
          "/api/guide/" + encodeURIComponent(documentKey) + "/comments",
          {
            method: "POST",
            body: {
              anchor: block.dataset.anchor,
              blockIndex: Number(block.dataset.blockIndex),
              snippet: remoteSnippet(block),
              text: text,
              pageUrl: pageUrl(),
            },
          },
        );
      },
      reply: function (thread, text) {
        return request(
          "/api/guide/" + encodeURIComponent(documentKey) + "/comments",
          {
            method: "POST",
            body: {
              parentCommentId: thread.id,
              text: text,
              pageUrl: pageUrl(),
            },
          },
        );
      },
      edit: function (item, text) {
        return request("/api/guide/comments/" + item.id, {
          method: "PATCH",
          body: { text: text, expectedUpdatedAt: item.updatedAt },
        });
      },
      withdraw: function (item) {
        return request("/api/guide/comments/" + item.id + "/withdraw", {
          method: "POST",
          body: {},
        });
      },
      patch: function (item, values) {
        values.expectedUpdatedAt = item.updatedAt;
        return request("/api/guide/comments/" + item.id, {
          method: "PATCH",
          body: values,
        });
      },
      remove: function (item) {
        return request("/api/guide/comments/" + item.id, { method: "DELETE" });
      },
      flag: function (anchor, note) {
        return request(
          "/api/guide/" + encodeURIComponent(documentKey) + "/review-flags",
          {
            method: "POST",
            body: { anchor: anchor, note: note, pageUrl: pageUrl() },
          },
        );
      },
      clearFlag: function (flag) {
        return request(
          "/api/guide/" +
            encodeURIComponent(documentKey) +
            "/review-flags/" +
            flag.id,
          { method: "DELETE" },
        );
      },
      subscribe: function () {
        schedulePoll(0);
        return stopPolling;
      },
    };

    // Cleared flags are fetched only while the Review tab shows All.
    function loadClearedFlags() {
      if (!showCleared || isClosed() || !validAuth() || !documentInfo || !documentInfo.permissions.canView) {
        clearedFlags = [];
        return Promise.resolve();
      }
      return store.clearedFlags().then(function (result) {
        clearedFlags = (result.reviewFlags || []).filter(function (flag) {
          return flag.clearedAt && (isAuthor() || flagInScope(flag));
        });
      });
    }

    // The contract's scope rule (5.3.1) for flags the hub returned without
    // it: written on this label, or before the label was published.
    function flagInScope(flag) {
      if (typeof flag.inScope === "boolean") {
        return flag.inScope;
      }
      if (!labelPolicy || labelPolicy.commentMode === "open") {
        return true;
      }
      if (flag.madeOnLabel === labelPolicy.label) {
        return true;
      }
      return !!(
        labelPolicy.publishedAt &&
        Date.parse(flag.createdAt) < Date.parse(labelPolicy.publishedAt)
      );
    }

    // For authors: where an item was written, and whether it is from another
    // version (outside this release's scope).
    function versionNotes(node, item, topLevel) {
      if (!isAuthor()) {
        return;
      }
      var outside = topLevel && item.inScope === false;
      if (outside) {
        node.classList.add("guide-other-version");
        node.insertBefore(
          element(
            "p",
            "guide-other-version__note",
            "From another version" +
              (item.madeOnLabel ? " (" + item.madeOnLabel + ")" : ""),
          ),
          node.firstChild,
        );
      } else if (item.madeOnLabel) {
        var meta = node.querySelector(".guide-comment__meta, .guide-card-label");
        (meta || node).appendChild(
          element("span", "guide-written-on", "Written on " + item.madeOnLabel),
        );
      }
    }

    function remoteSnippet(block) {
      return plainText(block).slice(0, 120);
    }

    function remotePlacement(thread) {
      var anchor = document.getElementById(thread.anchor);
      if (!anchor) {
        return null;
      }
      var candidates = areaBlocks(thread.anchor);
      var exact = candidates.filter(function (block) {
        return Number(block.dataset.blockIndex) === Number(thread.blockIndex);
      })[0];
      var textMatch = candidates.filter(function (block) {
        var snippet = normalizeRemote(thread.snippet).toLowerCase();
        return (
          snippet &&
          remoteSnippet(block).toLowerCase().indexOf(snippet.slice(0, 50)) === 0
        );
      })[0];
      return textMatch || exact || areaStart(anchor);
    }

    function person(user) {
      if (!user) {
        return "Unknown commenter";
      }
      return (
        user.displayName + (user.organization ? ", " + user.organization : "")
      );
    }

    // "mine" comes from the hub. A hub that predates it gets the same answer
    // from the author's user ID.
    function wroteIt(item) {
      if (typeof item.mine === "boolean") {
        return item.mine;
      }
      return !!(auth && auth.user && item.author && item.author.userId === auth.user.userId);
    }

    // Mine: threads the reader started or replied to.
    function involvesMe(thread) {
      return (
        wroteIt(thread) ||
        (thread.replies || []).some(function (reply) {
          return !reply.deleted && wroteIt(reply);
        })
      );
    }

    function itemElement(item, parent) {
      var node = document.createElement("article");
      node.className = "guide-comment" + (parent ? " guide-reply" : "");
      node.id = "comment-" + item.id;
      var meta = document.createElement("div");
      meta.className = "guide-comment__meta";
      var author = document.createElement("span");
      author.className = "guide-comment__author";
      author.textContent = person(item.author);
      meta.appendChild(author);
      if (wroteIt(item)) {
        meta.appendChild(element("span", "guide-comment__mine", "You"));
      }
      var when = document.createElement("time");
      when.textContent =
        new Date(item.createdAt).toLocaleString() +
        (item.editedAt ? " · edited" : "");
      meta.appendChild(when);
      node.appendChild(meta);
      var body = document.createElement("p");
      body.className = "guide-comment__text";
      body.textContent =
        item.state === "WITHDRAWN" || item.withdrawn
          ? "Withdrawn by the commenter."
          : item.text;
      node.appendChild(body);
      if (!parent) {
        var state = document.createElement("p");
        state.className = "guide-comment__state";
        state.textContent = "State: " + item.state.toLowerCase();
        node.appendChild(state);
        if (item.disposition) {
          var disposition = document.createElement("p");
          disposition.className = "guide-comment__disposition";
          disposition.textContent =
            item.disposition.label + ": " + item.changeNote;
          node.appendChild(disposition);
          var disposed = document.createElement("p");
          disposed.className = "aira-meta";
          disposed.textContent =
            "Disposed by " +
            person(item.disposedBy) +
            " on " +
            new Date(item.disposedAt).toLocaleString();
          node.appendChild(disposed);
        }
        if (item.state === "CLOSED") {
          node.classList.add("guide-comment--closed");
        }
      }
      versionNotes(node, item, !parent);
      var permissions = item.permissions || {};
      if (
        permissions.canEdit ||
        permissions.canWithdraw ||
        permissions.canDelete ||
        (!parent &&
          (permissions.canReply ||
            permissions.canDispose ||
            permissions.canClose ||
            permissions.canReattach))
      ) {
        var tools = document.createElement("div");
        tools.className = "guide-comment__tools";
        if (
          permissions.canReply &&
          !parent &&
          documentInfo &&
          documentInfo.isActive
        ) {
          addTool(tools, "Reply", function () {
            openRemoteForm(
              node,
              "Reply",
              function (text) {
                return store.reply(item, text);
              },
              "",
              true,
              { draft: "reply:" + item.id },
            );
          });
        }
        if (permissions.canEdit) {
          addTool(tools, "Edit", function () {
            openRemoteForm(
              node,
              "Save",
              function (text) {
                return store.edit(item, text);
              },
              item.text,
              false,
              { draft: "edit:" + item.id },
            );
          });
        }
        if (permissions.canWithdraw) {
          addTool(tools, "Withdraw", function () {
            openConfirmation(
              node,
              "Withdraw this comment?",
              "Withdraw",
              function () {
                return store.withdraw(item).then(acceptThread);
              },
            );
          });
        }
        if (!parent && permissions.canDispose) {
          addTool(
            tools,
            item.disposition ? "Change disposition" : "Dispose",
            function () {
              openDispositionForm(node, item);
            },
          );
          if (item.disposition) {
            addTool(tools, "Clear disposition", function () {
              store
                .patch(item, { dispositionCode: null })
                .then(acceptThread)
                .catch(showConflict);
            });
          }
        }
        if (!parent && permissions.canClose) {
          addTool(
            tools,
            item.state === "CLOSED" ? "Reopen" : "Close",
            function () {
              store
                .patch(item, {
                  state: item.state === "CLOSED" ? "OPEN" : "CLOSED",
                })
                .then(acceptThread)
                .catch(showConflict);
            },
          );
        }
        if (!parent && permissions.canReattach && !remotePlacement(item)) {
          addTool(tools, "Re-attach", function () {
            openReattachForm(node, item);
          });
        }
        if (permissions.canDelete) {
          addTool(tools, "Delete", function () {
            openConfirmation(
              node,
              "Delete this for inappropriate content?",
              "Delete",
              function () {
                return store.remove(item).then(function () {
                  if (parent) {
                    parent.replies = parent.replies.filter(function (reply) {
                      return reply.id !== item.id;
                    });
                    acceptThread(parent);
                  } else {
                    threads = threads.filter(function (thread) {
                      return thread.id !== item.id;
                    });
                    renderRemote();
                  }
                });
              },
            );
          });
        }
        node.appendChild(tools);
      }
      if (!parent) {
        (item.replies || []).forEach(function (reply) {
          node.appendChild(itemElement(reply, item));
        });
      }
      return node;
    }

    function addTool(holder, label, action) {
      var button = document.createElement("button");
      button.type = "button";
      button.textContent = label;
      button.addEventListener("click", action);
      holder.appendChild(button);
    }

    function showConflict(error) {
      if (error.status === 409 && error.body && error.body.current) {
        acceptThread(error.body.current);
        renderIdentity(
          "Someone else changed this comment. The current version is shown.",
        );
      } else {
        showStatusError(error);
      }
    }

    function openConfirmation(target, message, label, operation) {
      var old = target.querySelector(":scope > .guide-confirmation");
      if (old) {
        old.remove();
      }
      var prompt = document.createElement("div");
      prompt.className = "guide-confirmation";
      var text = document.createElement("p");
      text.textContent = message;
      prompt.appendChild(text);
      var yes = document.createElement("button");
      yes.type = "button";
      yes.textContent = label;
      yes.addEventListener("click", function () {
        operation()
          .then(function () {
            prompt.remove();
          })
          .catch(showConflict);
      });
      prompt.appendChild(yes);
      var cancel = document.createElement("button");
      cancel.type = "button";
      cancel.textContent = "Cancel";
      cancel.addEventListener("click", function () {
        prompt.remove();
      });
      prompt.appendChild(cancel);
      target.appendChild(prompt);
    }

    function openDispositionForm(target, item) {
      var form = document.createElement("form");
      form.className = "guide-comment-form guide-author-form";
      var select = document.createElement("select");
      select.required = true;
      select.setAttribute("aria-label", "Disposition");
      (documentInfo.dispositions || []).forEach(function (choice) {
        var option = document.createElement("option");
        option.value = choice.code;
        option.textContent = choice.label;
        option.selected =
          item.disposition && item.disposition.code === choice.code;
        select.appendChild(option);
      });
      form.appendChild(select);
      var note = document.createElement("textarea");
      note.required = true;
      note.maxLength = 500;
      note.placeholder = "Change note (required)";
      note.setAttribute("aria-label", "Change note");
      note.value = item.changeNote || "";
      form.appendChild(note);
      var save = document.createElement("button");
      save.type = "submit";
      save.textContent = "Save disposition";
      form.appendChild(save);
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        store
          .patch(item, {
            dispositionCode: select.value,
            changeNote: note.value.trim(),
          })
          .then(acceptThread)
          .catch(showConflict);
      });
      target.appendChild(form);
      note.focus();
    }

    function anchorChoices() {
      var seen = {};
      return remoteBlocks.filter(function (block) {
        if (seen[block.dataset.anchor]) {
          return false;
        }
        seen[block.dataset.anchor] = true;
        return true;
      });
    }

    function openReattachForm(target, item) {
      var form = document.createElement("form");
      form.className = "guide-comment-form guide-author-form";
      var select = document.createElement("select");
      select.setAttribute("aria-label", "Attach to");
      anchorChoices().forEach(function (block) {
        var option = document.createElement("option");
        option.value = block.dataset.anchor;
        var anchor = document.getElementById(block.dataset.anchor);
        option.textContent =
          (anchor && plainText(anchor).slice(0, 80)) ||
          plainText(block).slice(0, 80) ||
          block.dataset.anchor;
        select.appendChild(option);
      });
      form.appendChild(select);
      var save = document.createElement("button");
      save.type = "submit";
      save.textContent = "Save attachment";
      form.appendChild(save);
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        var block = areaBlocks(select.value)[0];
        store
          .patch(item, {
            anchor: select.value,
            blockIndex: Number(block.dataset.blockIndex),
            snippet: remoteSnippet(block),
          })
          .then(acceptThread)
          .catch(showConflict);
      });
      target.appendChild(form);
    }

    function renderRemote(preserveOpenForms) {
      var openThreads = {};
      var activeControl = null;
      var selectionStart = null;
      var selectionEnd = null;
      if (preserveOpenForms) {
        if (
          document.activeElement &&
          document.activeElement.closest &&
          document.activeElement.closest(".guide-comment-form")
        ) {
          activeControl = document.activeElement;
          selectionStart = activeControl.selectionStart;
          selectionEnd = activeControl.selectionEnd;
        }
        toArray(
          document.querySelectorAll("#guide-list-comments .guide-comment[id^='comment-']"),
        ).forEach(function (node) {
          if (node.querySelector(".guide-comment-form")) {
            openThreads[node.id.slice("comment-".length)] = node;
          }
        });
      }
      pruneEmptyHolders();
      threads = threads.filter(function (thread) {
        return !thread.deleted;
      });
      if (!validAuth()) {
        annotations.setCommentsUnavailable("Sign in to see comments");
      } else if (isClosed()) {
        annotations.setCommentsUnavailable("Comments are closed on this version");
      } else {
        var placed = [];
        var orphans = [];
        threads.forEach(function (thread) {
          if (thread.state === "CLOSED" && !showClosed) {
            return;
          }
          var target = remotePlacement(thread);
          var entry = {
            target: target,
            element: openThreads[String(thread.id)] || itemElement(thread, null),
            open: thread.state === "OPEN" || thread.state === "DISPOSED",
            counted: thread.inScope !== false,
            mine: involvesMe(thread),
          };
          (target ? placed : orphans).push(entry);
        });
        annotations.setComments(placed, orphans);
      }
      renderReviewFlags(preserveOpenForms);
      followRemoteHash();
      if (activeControl && document.body.contains(activeControl)) {
        activeControl.focus({ preventScroll: true });
        if (selectionStart !== null && activeControl.setSelectionRange) {
          activeControl.setSelectionRange(selectionStart, selectionEnd);
        }
      }
    }

    function flagFor(anchor) {
      return (
        reviewFlags.filter(function (flag) {
          return flag.anchor === anchor;
        })[0] || null
      );
    }

    // host is where the form opens: under the area's block in the text, or
    // in the flag's card in the panel.
    function openFlagForm(anchor, host) {
      var existing = flagFor(anchor);
      openRemoteForm(
        host,
        existing ? "Save review flag" : "Flag for review",
        function (note) {
          return store.flag(anchor, note).then(function (flag) {
            reviewFlags = reviewFlags.filter(function (current) {
              return current.anchor !== flag.anchor;
            });
            reviewFlags.push(flag);
            renderRemote();
            return null;
          });
        },
        existing ? existing.note : "",
        false,
        { draft: "flag:" + anchor, maxLength: 500 },
      );
    }

    function clearReviewFlag(flag) {
      store
        .clearFlag(flag)
        .then(function () {
          reviewFlags = reviewFlags.filter(function (current) {
            return current.id !== flag.id;
          });
          if (openFlagAnchor === flag.anchor) {
            openFlagAnchor = null;
          }
          return loadClearedFlags();
        })
        .then(function () {
          renderRemote();
        })
        .catch(showStatusError);
    }

    function isAuthor() {
      return !!(documentInfo && documentInfo.permissions.isAuthor);
    }

    function flaggedBy(flag) {
      var stamp = flag.updatedAt || flag.createdAt;
      return (
        "Flagged by " +
        person(flag.createdBy) +
        (stamp ? ", " + new Date(stamp).toLocaleString() : "")
      );
    }

    // The marker that starts a flagged area: a badge that shows the note on
    // hover or focus, and keeps it open when clicked. Authors can edit or
    // clear the flag from it.
    function flagMarker(flag, block, inRow) {
      var marker = document.createElement(inRow ? "span" : "div");
      marker.className =
        "guide-flag-marker" + (inRow ? " guide-flag-marker--row" : "");
      var badge = document.createElement("button");
      badge.type = "button";
      badge.className = "guide-flag-badge";
      badge.setAttribute("aria-expanded", "false");
      var icon = document.createElement("span");
      icon.setAttribute("aria-hidden", "true");
      icon.textContent = "⚑";
      badge.appendChild(icon);
      var label = document.createElement("span");
      label.className = inRow
        ? "aira-visually-hidden"
        : "guide-flag-badge__label";
      label.textContent = "Review";
      badge.appendChild(label);
      if (!inRow) {
        var excerpt = document.createElement("span");
        excerpt.className = "guide-flag-badge__note";
        var text = normalizeRemote(flag.note);
        excerpt.textContent =
          text.length > 80 ? text.slice(0, 80) + "…" : text;
        badge.appendChild(excerpt);
      }
      marker.appendChild(badge);

      var popover = document.createElement("div");
      popover.className = "guide-flag-popover";
      popover.setAttribute("role", "group");
      popover.setAttribute("aria-label", "Review flag");
      var note = document.createElement("p");
      note.className = "guide-flag-popover__note";
      note.textContent = flag.note;
      popover.appendChild(note);
      popover.appendChild(element("p", "aira-meta", flaggedBy(flag)));
      if (isAuthor()) {
        var tools = document.createElement("div");
        tools.className = "guide-comment__tools";
        addTool(tools, "Edit", function () {
          setOpen(false);
          openFlagForm(flag.anchor, block);
        });
        addTool(tools, "Clear", function () {
          clearReviewFlag(flag);
        });
        popover.appendChild(tools);
      }
      marker.appendChild(popover);

      function setOpen(open) {
        marker.classList.toggle("is-open", open);
        badge.setAttribute("aria-expanded", open ? "true" : "false");
        openFlagAnchor = open ? flag.anchor : null;
      }
      badge.addEventListener("click", function () {
        setOpen(!marker.classList.contains("is-open"));
      });
      marker.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && marker.classList.contains("is-open")) {
          event.preventDefault();
          setOpen(false);
          badge.focus();
        }
      });
      if (openFlagAnchor === flag.anchor) {
        setOpen(true);
      }
      return marker;
    }

    // A flag in the Review tab, with the author's controls.
    function flagCard(flag, host) {
      var cleared = !!flag.clearedAt;
      var card = element(
        "article",
        "guide-flag-card" + (cleared ? " guide-flag-card--cleared" : ""),
      );
      card.id = "review-flag-" + flag.id;
      var label = element("p", "guide-card-label");
      label.appendChild(element("span", "", "⚑ ")).setAttribute(
        "aria-hidden",
        "true",
      );
      label.appendChild(document.createTextNode(cleared ? "Review flag (cleared)" : "Review flag"));
      card.appendChild(label);
      card.appendChild(element("p", "guide-card-note", flag.note));
      card.appendChild(element("p", "aira-meta", flaggedBy(flag)));
      versionNotes(card, { inScope: flagInScope(flag) ? true : false, madeOnLabel: flag.madeOnLabel }, true);
      if (cleared) {
        card.appendChild(
          element(
            "p",
            "aira-meta",
            "Cleared by " +
              person(flag.clearedBy) +
              ", " +
              new Date(flag.clearedAt).toLocaleString(),
          ),
        );
      } else if (isAuthor()) {
        var tools = element("div", "guide-comment__tools");
        if (host) {
          addTool(tools, "Edit", function () {
            openFlagForm(flag.anchor, card);
          });
        }
        addTool(tools, "Clear", function () {
          clearReviewFlag(flag);
        });
        card.appendChild(tools);
      }
      return card;
    }

    // A periodic refresh keeps any flag card with an open form.
    function renderReviewFlags(preserveOpenForms) {
      var openCards = {};
      if (preserveOpenForms) {
        toArray(
          document.querySelectorAll("#guide-list-review .guide-flag-card"),
        ).forEach(function (card) {
          if (card.querySelector(".guide-comment-form")) {
            openCards[card.id] = card;
          }
        });
      }
      toArray(
        content.querySelectorAll(".guide-flag-marker,.guide-flag-button"),
      ).forEach(function (node) {
        node.remove();
      });
      remoteBlocks.forEach(function (block) {
        block.classList.remove(
          "guide-review-flagged",
          "guide-review-flagged--continued",
        );
      });
      var placed = [];
      var notPlaced = [];
      (isClosed() ? [] : reviewFlags).forEach(function (flag) {
        var area = areaBlocks(flag.anchor);
        var anchor = document.getElementById(flag.anchor);
        if (area.length && isRowBlock(area[0])) {
          area[0].classList.add("guide-review-flagged");
          if (area[0].cells.length) {
            area[0].cells[0].insertBefore(
              flagMarker(flag, area[0], true),
              area[0].cells[0].firstChild,
            );
          }
        } else if (area.length) {
          area[0].parentNode.insertBefore(
            flagMarker(flag, area[0], false),
            area[0],
          );
          area.forEach(function (block) {
            block.classList.add("guide-review-flagged");
            var previous = block.previousElementSibling;
            if (
              previous &&
              (previous.classList.contains("guide-flag-marker") ||
                (previous.classList.contains("guide-review-flagged") &&
                  previous.dataset.anchor === flag.anchor))
            ) {
              block.classList.add("guide-review-flagged--continued");
            }
          });
        }
        var target = area[0] || (anchor ? areaStart(anchor) : null);
        var host = area[0] || null;
        var entry = {
          target: target,
          element: openCards["review-flag-" + flag.id] || flagCard(flag, host),
          open: true,
          counted: flag.inScope !== false,
          ticks: area.length ? area : target ? [target] : [],
        };
        (target ? placed : notPlaced).push(entry);
      });
      clearedFlags.forEach(function (flag) {
        var area = areaBlocks(flag.anchor);
        var anchor = document.getElementById(flag.anchor);
        var target = area[0] || (anchor ? areaStart(anchor) : null);
        var entry = { target: target, element: flagCard(flag, null), open: false };
        (target ? placed : notPlaced).push(entry);
      });
      annotations.setFlags(placed, notPlaced);
      if (isAuthor()) {
        remoteBlocks.forEach(function (block) {
          var flagged = !!flagFor(block.dataset.anchor);
          var button = document.createElement("button");
          button.type = "button";
          button.className =
            "guide-flag-button" + (flagged ? " guide-flag-button--active" : "");
          button.textContent = "⚑";
          button.title = flagged ? "Edit review flag" : "Flag for review";
          button.setAttribute(
            "aria-label",
            flagged ? "Edit the review flag on this area" : "Flag this area for review",
          );
          button.addEventListener("click", function () {
            openFlagForm(block.dataset.anchor, block);
          });
          controlHost(block).appendChild(button);
        });
      }
      markFlaggedNav();
    }

    function commentButtons() {
      return remoteBlocks
        .map(function (block) {
          return controlHost(block).querySelector(":scope > .guide-comment-button");
        })
        .filter(Boolean);
    }

    function renderIdentity(message) {
      status.textContent = "";
      if (message) {
        var note = document.createElement("p");
        note.className = "guide-form-error";
        note.textContent = message;
        status.appendChild(note);
      }
      if (!validAuth()) {
        // Signed out, the comment buttons still appear; they lead here.
        commentButtons().forEach(function (button) {
          button.hidden = false;
        });
        status.appendChild(
          element(
            "p",
            "aira-meta",
            "Sign in with your InteropHub account to see comments and add your own.",
          ),
        );
        var signIn = document.createElement("button");
        signIn.type = "button";
        signIn.id = "guide-sign-in";
        signIn.className =
          "aira-button aira-button--primary aira-button--small";
        signIn.textContent = "Sign in to comment";
        signIn.addEventListener("click", function () {
          beginSignIn(false);
        });
        status.appendChild(signIn);
        return;
      }
      commentButtons().forEach(function (button) {
        button.hidden = !(
          documentInfo &&
          documentInfo.isActive &&
          documentInfo.permissions.canComment
        );
      });
      var identity = element("div", "guide-identity");
      identity.appendChild(
        element("span", "aira-meta", "Signed in as " + person(auth.user)),
      );
      var signOut = document.createElement("button");
      signOut.type = "button";
      signOut.className = "aira-button aira-button--link";
      signOut.textContent = "Sign out";
      signOut.addEventListener("click", function () {
        revoke(false);
      });
      identity.appendChild(signOut);
      var switchUser = document.createElement("button");
      switchUser.type = "button";
      switchUser.className = "aira-button aira-button--link";
      switchUser.textContent = "Not you?";
      switchUser.addEventListener("click", function () {
        revoke(true);
      });
      identity.appendChild(switchUser);
      status.appendChild(identity);
      if (documentInfo && !documentInfo.permissions.canView) {
        var denied = document.createElement("p");
        denied.textContent =
          "Your account cannot see comments on this document.";
        status.appendChild(denied);
      }
      if (documentInfo && !documentInfo.isActive) {
        var inactive = document.createElement("p");
        inactive.textContent = "Comments on this document are read-only.";
        status.appendChild(inactive);
      }
    }

    function beginSignIn(promptLogin) {
      var chars =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~";
      var bytes = new Uint8Array(64);
      window.crypto.getRandomValues(bytes);
      var verifier = Array.prototype.map
        .call(bytes, function (value) {
          return chars[value % chars.length];
        })
        .join("");
      var stateBytes = new Uint8Array(24);
      window.crypto.getRandomValues(stateBytes);
      var state = base64url(stateBytes);
      var returnTo = window.location.origin + window.location.pathname;
      var returnLocation = new URL(window.location.href);
      returnLocation.searchParams.delete("interophub");
      writeJson(window.sessionStorage, authKey, {
        codeVerifier: verifier,
        state: state,
        returnLocation: returnLocation.href,
      });
      window.crypto.subtle
        .digest("SHA-256", new TextEncoder().encode(verifier))
        .then(function (digest) {
          var query = new URLSearchParams({
            app_code: "topic-reference",
            return_to: returnTo,
            state: state,
            code_challenge: base64url(new Uint8Array(digest)),
            code_challenge_method: "S256",
            response_mode: "fragment",
            requested_url: returnTo,
          });
          if (promptLogin) {
            query.set("prompt", "login");
          }
          window.top.location.href = hub + "/home?" + query.toString();
        });
    }

    function base64url(bytes) {
      var binary = "";
      bytes.forEach(function (value) {
        binary += String.fromCharCode(value);
      });
      return window
        .btoa(binary)
        .replace(/\+/g, "-")
        .replace(/\//g, "_")
        .replace(/=+$/, "");
    }

    function finishSignIn() {
      var params = new URLSearchParams(window.location.hash.slice(1));
      if (!params.has("code")) {
        return Promise.resolve(false);
      }
      var pendingAuth = readJson(window.sessionStorage, authKey);
      if (!pendingAuth || params.get("state") !== pendingAuth.state) {
        writeJson(window.sessionStorage, authKey, null);
        history.replaceState(
          null,
          "",
          window.location.pathname + window.location.search,
        );
        renderIdentity("Sign-in did not complete. Try again.");
        return Promise.resolve(true);
      }
      var returnTo = window.location.origin + window.location.pathname;
      return request("/api/guide/token", {
        token: false,
        method: "POST",
        body: {
          code: params.get("code"),
          codeVerifier: pendingAuth.codeVerifier,
          returnTo: returnTo,
        },
      })
        .then(function (result) {
          auth = {
            accessToken: result.accessToken,
            expiresAt: result.expiresAt,
            user: result.user,
          };
          writeJson(window.localStorage, tokenKey, auth);
          writeJson(window.sessionStorage, authKey, null);
          history.replaceState(null, "", pendingAuth.returnLocation);
          return true;
        })
        .catch(function (error) {
          writeJson(window.sessionStorage, authKey, null);
          history.replaceState(
            null,
            "",
            window.location.pathname + window.location.search,
          );
          renderIdentity(errorMessage(error));
          return true;
        });
    }

    function revoke(switchAccount) {
      request("/api/guide/token", { method: "DELETE" })
        .catch(function () {})
        .then(function () {
          auth = null;
          writeJson(window.localStorage, tokenKey, null);
          threads = [];
          reviewFlags = [];
          clearedFlags = [];
          documentInfo = null;
          renderRemote();
          renderIdentity();
          if (switchAccount) {
            beginSignIn(true);
          }
        });
    }

    function acknowledged() {
      var key = noticePrefix + auth.user.userId;
      try {
        return !!window.localStorage.getItem(key);
      } catch (error) {
        return false;
      }
    }

    // options.draft names the form for its saved draft (for example
    // "add:<anchor>"); options.maxLength matches the hub's limit for the field.
    function openRemoteForm(
      target,
      label,
      operation,
      initial,
      needsNotice,
      options,
    ) {
      options = options || {};
      var maxLength = options.maxLength || 4000;
      target = formHost(target);
      var old = target.querySelector(":scope > .guide-comment-form");
      if (old) {
        old.remove();
      }
      var form = document.createElement("form");
      form.className = "guide-comment-form";
      var textarea = document.createElement("textarea");
      textarea.className = "aira-textarea";
      textarea.required = true;
      textarea.maxLength = maxLength;
      textarea.setAttribute("aria-label", label);
      var saved = readDraft(options.draft);
      var restored = saved && saved !== (initial || "");
      textarea.value = restored ? saved : initial || "";
      form.appendChild(textarea);
      var counter = document.createElement("p");
      counter.className = "aira-meta guide-form-count";
      form.appendChild(counter);
      function updateCounter() {
        var used = textarea.value.length;
        counter.hidden = used < maxLength * 0.75;
        counter.textContent =
          used.toLocaleString() + " / " + maxLength.toLocaleString() + " characters";
      }
      updateCounter();
      textarea.addEventListener("input", function () {
        updateCounter();
        writeDraft(
          options.draft,
          textarea.value === (initial || "") ? "" : textarea.value,
        );
      });
      if (restored) {
        var draftNote = document.createElement("p");
        draftNote.className = "aira-meta guide-form-draft";
        draftNote.appendChild(
          document.createTextNode("Restored your unsaved draft. "),
        );
        var discard = document.createElement("button");
        discard.type = "button";
        discard.className = "aira-button aira-button--link";
        discard.textContent = "Discard draft";
        discard.addEventListener("click", function () {
          writeDraft(options.draft, "");
          textarea.value = initial || "";
          updateCounter();
          draftNote.remove();
          textarea.focus();
        });
        draftNote.appendChild(discard);
        form.insertBefore(draftNote, textarea);
      }
      var notice = null;
      if (needsNotice && !acknowledged()) {
        var noticeLabel = document.createElement("label");
        notice = document.createElement("input");
        notice.type = "checkbox";
        notice.required = true;
        noticeLabel.appendChild(notice);
        noticeLabel.appendChild(
          document.createTextNode(
            " Other signed-in users will see this comment with your name and organization.",
          ),
        );
        form.appendChild(noticeLabel);
      }
      var error = document.createElement("p");
      error.className = "guide-form-error";
      form.appendChild(error);
      var actions = element("div", "guide-comment-actions");
      var submit = document.createElement("button");
      submit.type = "submit";
      submit.className = "aira-button aira-button--primary aira-button--small";
      submit.textContent = label;
      actions.appendChild(submit);
      var cancel = document.createElement("button");
      cancel.type = "button";
      cancel.className = "aira-button aira-button--ghost aira-button--small";
      cancel.textContent = "Cancel";
      cancel.addEventListener("click", function () {
        form.remove();
        pruneEmptyHolders();
      });
      actions.appendChild(cancel);
      form.appendChild(actions);
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        var value = textarea.value.trim();
        if (!value || (notice && !notice.checked)) {
          return;
        }
        if (notice) {
          try {
            window.localStorage.setItem(noticePrefix + auth.user.userId, "yes");
          } catch (storageError) {}
        }
        submit.disabled = true;
        error.textContent = "";
        operation(value)
          .then(function (thread) {
            writeDraft(options.draft, "");
            form.remove();
            if (thread) {
              acceptThread(thread);
            }
            pruneEmptyHolders();
          })
          .catch(function (failure) {
            submit.disabled = false;
            if (
              failure &&
              failure.status === 403 &&
              failure.body &&
              failure.body.error === "comments_closed"
            ) {
              // Keep the form and its draft, as for a blocked request; the
              // next refresh shows the version as closed.
              writeDraft(
                options.draft,
                textarea.value === (initial || "") ? "" : textarea.value,
              );
              form.classList.add("guide-comment-form--refused");
              submit.disabled = true;
              error.textContent =
                "Comments are closed on this version. Your text is still here and saved in this browser.";
              labelPolicy = Object.assign(
                { label: null, display: null, publishedAt: null },
                labelPolicy || {},
                { commentMode: "closed" },
              );
              applyPolicy();
              // A form in the text survives the redraw; one in the panel is
              // left as it is, with its message, until the next refresh.
              if (!form.closest("#guide-annotations")) {
                renderRemote(true);
              }
              return;
            }
            writeDraft(
              options.draft,
              textarea.value === (initial || "") ? "" : textarea.value,
            );
            error.textContent =
              errorMessage(failure) +
              (failure && (failure.blocked || failure.network)
                ? " Your text is still here and saved in this browser."
                : "");
          });
      });
      target.appendChild(form);
      textarea.focus();
    }

    function acceptThread(thread) {
      var found = false;
      threads = threads.map(function (current) {
        if (current.id === thread.id) {
          found = true;
          return thread;
        }
        return current;
      });
      if (!found) {
        threads.push(thread);
      }
      renderRemote();
      restartPolling();
    }

    function showStatusError(error) {
      if (!error.handled) {
        renderIdentity(errorMessage(error));
      }
    }

    function mergeChanges(changes) {
      var changed = false;
      (changes || []).forEach(function (incoming) {
        var index = threads.findIndex(function (thread) {
          return thread.id === incoming.id;
        });
        if (incoming.deleted) {
          if (index >= 0) {
            threads.splice(index, 1);
            changed = true;
          }
          return;
        }
        if (index >= 0) {
          threads[index] = incoming;
        } else {
          threads.push(incoming);
        }
        changed = true;
      });
      return changed;
    }

    function poll() {
      if (
        document.hidden ||
        !validAuth() ||
        !serverTime ||
        !documentInfo ||
        !documentInfo.permissions.canView
      ) {
        return;
      }
      request(
        "/api/guide/" +
          encodeURIComponent(documentKey) +
          "/comments" +
          commentsQuery("since=" + encodeURIComponent(serverTime)),
      )
        .then(function (result) {
          serverTime = result.serverTime;
          reviewFlags = result.reviewFlags || [];
          if (acceptPolicy(result)) {
            // A refresh carries only changed threads, never ones the new mode
            // hides or reveals, so a changed mode means reading everything again.
            store
              .load()
              .then(function () {
                renderRemote(true);
                restartPolling();
              })
              .catch(showStatusError);
            return;
          }
          var changed = mergeChanges(result.comments);
          renderRemote(true);
          pollStep = changed
            ? 0
            : Math.min(pollStep + 1, pollDelays.length - 1);
          schedulePoll(pollDelays[pollStep]);
        })
        .catch(function (error) {
          if (!error.handled) {
            schedulePoll(
              pollDelays[Math.min(++pollStep, pollDelays.length - 1)],
            );
          }
        });
    }

    function schedulePoll(delay) {
      stopPolling();
      if (!document.hidden) {
        pollTimer = window.setTimeout(poll, delay === 0 ? 30000 : delay);
      }
    }
    function stopPolling() {
      if (pollTimer) {
        window.clearTimeout(pollTimer);
        pollTimer = null;
      }
    }
    function restartPolling() {
      pollStep = 0;
      schedulePoll(30000);
    }

    function followRemoteHash() {
      var match = window.location.hash.match(/^#comment-(\d+)$/);
      if (!match) {
        return;
      }
      var item = document.getElementById("comment-" + match[1]);
      if (item && !item.classList.contains("guide-comment--target")) {
        item.classList.add("guide-comment--target");
        annotations.reveal("comments", item);
      }
    }

    remoteBlocks.forEach(function (block) {
      block.classList.add("guide-block");
      var button = document.createElement("button");
      button.type = "button";
      button.className = "guide-comment-button";
      button.textContent = "\u{1F4AC}";
      button.title = "Comment on this";
      button.setAttribute("aria-label", "Comment on this paragraph");
      button.addEventListener("click", function () {
        if (!validAuth()) {
          annotations.open("comments");
          var signIn = document.getElementById("guide-sign-in");
          if (signIn) {
            signIn.focus();
          }
          return;
        }
        if (
          documentInfo &&
          documentInfo.isActive &&
          documentInfo.permissions.canComment
        ) {
          openRemoteForm(
            block,
            "Add comment",
            function (text) {
              return store.add(block, text).then(function (thread) {
                acceptThread(thread);
                annotations.reveal(
                  "comments",
                  document.getElementById("comment-" + thread.id),
                );
                return null;
              });
            },
            "",
            true,
            { draft: "add:" + block.dataset.anchor },
          );
        }
      });
      controlHost(block).appendChild(button);
    });
    window.addEventListener("hashchange", followRemoteHash);
    document.addEventListener("visibilitychange", function () {
      if (document.hidden) {
        stopPolling();
      } else {
        pollStep = 0;
        poll();
      }
    });

    finishSignIn().then(function () {
      var marker =
        new URL(window.location.href).searchParams.get("interophub") ===
        "signin";
      if (marker) {
        var clean = new URL(window.location.href);
        clean.searchParams.delete("interophub");
        history.replaceState(null, "", clean.href);
        if (!validAuth()) {
          beginSignIn(false);
          return;
        }
      }
      renderIdentity();
      if (validAuth()) {
        store
          .load()
          .then(function () {
            renderIdentity();
            renderRemote();
            store.subscribe();
          })
          .catch(showStatusError);
      } else {
        renderRemote();
      }
    });
  }
});
