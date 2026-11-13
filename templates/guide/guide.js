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

  function renderSubnav(section) {
    subnav.textContent = "";
    railTitle.textContent = section ? headingText(section) : "On this page";
    var subsections = section
      ? section.querySelectorAll(":scope > section.level3")
      : [];
    if (!subsections.length) {
      var empty = document.createElement("li");
      empty.className = "guide-subnav-empty";
      empty.textContent = "No subsections";
      subnav.appendChild(empty);
      return;
    }
    Array.prototype.forEach.call(subsections, function (sub) {
      var item = document.createElement("li");
      var link = document.createElement("a");
      link.href = "#" + sub.id;
      link.textContent = headingText(sub);
      item.appendChild(link);
      subnav.appendChild(item);
    });
    markFlaggedNav();
  }

  // Mark section and subsection links whose section holds a review flag.
  var flaggedNavTitle = "Has areas flagged for review";
  function markFlaggedNav() {
    sectionLinks
      .concat(Array.prototype.slice.call(subnav.querySelectorAll("a")))
      .forEach(function (link) {
        var href = link.getAttribute("href") || "";
        var target =
          href.charAt(0) === "#" ? document.getElementById(href.slice(1)) : null;
        var flagged = !!(
          target && target.querySelector(".guide-review-flagged")
        );
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
        if (section && link.getAttribute("href") === "#" + section.id) {
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
        subnav.querySelectorAll("a"),
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

  var panel = document.getElementById("guide-comments-panel");
  var nameInput = document.getElementById("guide-commenter");
  var countBadge = document.getElementById("guide-comment-count");
  var index = document.getElementById("guide-comment-index");
  var toggle = document.getElementById("guide-comments-toggle");
  panel.hidden = false;
  nameInput.value = load(NAME_KEY) || "";
  nameInput.addEventListener("change", function () {
    store(NAME_KEY, nameInput.value.trim());
  });

  function save() {
    localStore.persist();
  }

  function normalize(text) {
    return (text || "").replace(/\s+/g, " ").trim();
  }

  function blockSnippet(block) {
    var copy = block.cloneNode(true);
    Array.prototype.forEach.call(
      copy.querySelectorAll(".guide-comment-button"),
      function (button) {
        button.remove();
      },
    );
    return normalize(copy.textContent).slice(0, 120);
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

  // A table row is a comment block when its table names each row (see
  // "Review anchors"). Its controls go in its last cell; its threads and forms
  // go in a full-width row inserted after it, so the table stays valid.
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

  function threadAfter(target) {
    var holder;
    if (isRowBlock(target)) {
      var cell = rowExtra(target);
      holder = cell.querySelector(":scope > .guide-thread");
      if (!holder) {
        holder = document.createElement("div");
        holder.className = "guide-thread";
        cell.insertBefore(holder, cell.firstChild);
      }
      return holder;
    }
    var next = target.nextElementSibling;
    if (next && next.classList.contains("guide-thread")) {
      return next;
    }
    holder = document.createElement("div");
    holder.className = "guide-thread";
    target.insertAdjacentElement("afterend", holder);
    return holder;
  }

  function formHost(target) {
    return isRowBlock(target) ? rowExtra(target) : target;
  }

  function pruneRowExtras() {
    Array.prototype.forEach.call(
      content.querySelectorAll(".guide-row-extra"),
      function (row) {
        if (!row.cells[0] || !row.cells[0].firstElementChild) {
          row.remove();
        }
      },
    );
  }

  // Commentable blocks are annotated by the build with their anchor area.
  var BLOCK_SELECTOR = "[data-anchor][data-block-index]";
  var blocks = Array.prototype.filter.call(
    content.querySelectorAll(BLOCK_SELECTOR),
    function (element) {
      var parent = element.parentElement;
      while (parent && parent !== content) {
        if (parent.matches(BLOCK_SELECTOR)) {
          return false;
        }
        parent = parent.parentElement;
      }
      return true;
    },
  );

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
        return normalize(block.textContent).indexOf(comment.quote) !== -1;
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

  function anchorElement(name) {
    return document.getElementById(name);
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

  function placement(comment) {
    if (!comment.anchor) {
      var legacy = legacyBlock(comment);
      return legacy ? { block: legacy, target: legacy, orphaned: false } : null;
    }
    var anchor = anchorElement(comment.anchor);
    if (!anchor) {
      return null;
    }
    var areaBlocks = blocks.filter(function (block) {
      return block.dataset.anchor === comment.anchor;
    });
    var matches = areaBlocks.filter(function (block) {
      return snippetSimilarity(blockSnippet(block), comment.snippet) >= 0.75;
    });
    var preferred = matches.filter(function (block) {
      return block.dataset.blockIndex === String(comment.blockIndex);
    })[0];
    var block = preferred || matches[0] || null;
    return {
      block: block,
      target: block || areaStart(anchor),
      orphaned: false,
    };
  }

  function threadFor(block) {
    return threadAfter(block);
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
      var block = placed && placed.block;
      if (block) {
        openForm(block, comment.quote, comment);
      }
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

  function render() {
    Array.prototype.forEach.call(
      content.querySelectorAll(".guide-thread"),
      function (thread) {
        thread.remove();
      },
    );
    pruneRowExtras();
    index.textContent = "";
    var oldOrphans = content.querySelector(".guide-orphans");
    if (oldOrphans) {
      oldOrphans.remove();
    }
    comments.sort(function (a, b) {
      return (a.created || "").localeCompare(b.created || "");
    });
    var unplaced = [];
    comments.forEach(function (comment) {
      var placed = placement(comment);
      var block = placed && placed.block;
      if (placed) {
        threadFor(placed.target).appendChild(commentElement(comment));
      } else {
        unplaced.push(comment);
      }
      var entry = document.createElement("li");
      var link = document.createElement("a");
      link.href = "#comment-" + comment.id;
      link.textContent =
        (comment.author || "Anonymous") +
        ": " +
        normalize(comment.text).slice(0, 60) +
        (normalize(comment.text).length > 60 ? "…" : "");
      entry.appendChild(link);
      var where = document.createElement("span");
      where.className = "aira-meta";
      where.textContent = placed
        ? comment.anchor || comment.sectionTitle || comment.sectionId
        : "Orphaned comment";
      entry.appendChild(where);
      index.appendChild(entry);
    });
    countBadge.textContent = String(comments.length);
    if (unplaced.length) {
      var orphanGroup = document.createElement("section");
      orphanGroup.className = "guide-orphans";
      var orphanHeading = document.createElement("h2");
      orphanHeading.textContent = "Orphaned comments";
      orphanGroup.appendChild(orphanHeading);
      unplaced.forEach(function (comment) {
        var holder = document.createElement("div");
        holder.className = "guide-thread";
        holder.appendChild(commentElement(comment));
        orphanGroup.appendChild(holder);
      });
      content.appendChild(orphanGroup);
    }
    followHash();
  }

  function closeForms() {
    Array.prototype.forEach.call(
      content.querySelectorAll(".guide-comment-form"),
      function (form) {
        form.remove();
      },
    );
  }

  function sectionTitle(block) {
    var section = block.closest("section");
    return section ? headingText(section) : "";
  }

  function openForm(block, quote, existing) {
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
      if (existing) {
        localStore.edit(existing, text);
      } else {
        localStore.add({
          id: newId(),
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
    });
    form.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        closeForms();
      } else if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
        form.requestSubmit();
      }
    });

    var thread = threadFor(block);
    thread.appendChild(form);
    textarea.focus();
    if (!nameInput.value.trim()) {
      nameInput.classList.add("guide-flash");
    }
  }

  toggle.addEventListener("click", function () {
    var hidden = document.body.classList.toggle("guide-comments-hidden");
    toggle.setAttribute("aria-pressed", hidden ? "false" : "true");
    toggle.textContent = hidden ? "Show comments" : "Hide comments";
  });

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
      if (
        !comments.length ||
        (control.nextElementSibling &&
          control.nextElementSibling.classList.contains("guide-confirmation"))
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
      control.insertAdjacentElement("afterend", prompt);
    });

  function followHash() {
    Array.prototype.forEach.call(
      content.querySelectorAll(".guide-comment--target"),
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
    document.body.classList.remove("guide-comments-hidden");
    toggle.setAttribute("aria-pressed", "true");
    toggle.textContent = "Hide comments";
    comment.classList.add("guide-comment--target");
    comment.scrollIntoView({ block: "center" });
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
    var panel = document.getElementById("guide-comments-panel");
    var status = document.getElementById("guide-comments-status");
    var count = document.getElementById("guide-comment-count");
    var remoteIndex = document.getElementById("guide-comment-index");
    var remoteToggle = document.getElementById("guide-comments-toggle");
    var remoteBlocks = Array.prototype.slice.call(
      content.querySelectorAll("[data-anchor][data-block-index]"),
    );
    var threads = [];
    var reviewFlags = [];
    var openFlagAnchor = null;
    var showClosed = false;
    var documentInfo = null;
    var serverTime = null;
    var pollTimer = null;
    var pollStep = 0;
    var pollDelays = [30000, 60000, 600000, 1800000];
    var auth = readJson(window.localStorage, tokenKey);

    document.getElementById("guide-local-identity").hidden = true;
    Array.prototype.forEach.call(
      document.querySelectorAll(".guide-local-control"),
      function (item) {
        item.hidden = true;
      },
    );
    panel.hidden = false;

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
                (showClosed ? "?state=all" : ""),
            ).then(function (result) {
              threads = result.comments || [];
              reviewFlags = result.reviewFlags || [];
              serverTime = result.serverTime;
            });
          },
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
          { method: "POST", body: { anchor: anchor, note: note } },
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

    function remoteSnippet(block) {
      var copy = block.cloneNode(true);
      Array.prototype.forEach.call(
        copy.querySelectorAll(
          ".guide-comment-button,.guide-thread,.guide-flag-button,.guide-flag-marker,.guide-comment-form",
        ),
        function (node) {
          node.remove();
        },
      );
      return normalizeRemote(copy.textContent).slice(0, 120);
    }

    function remotePlacement(thread) {
      var anchor = document.getElementById(thread.anchor);
      if (!anchor) {
        return null;
      }
      var candidates = remoteBlocks.filter(function (block) {
        return block.dataset.anchor === thread.anchor;
      });
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
      return textMatch || exact || anchor;
    }

    function threadHolder(target) {
      return threadAfter(target);
    }

    function person(user) {
      if (!user) {
        return "Unknown commenter";
      }
      return (
        user.displayName + (user.organization ? ", " + user.organization : "")
      );
    }

    function itemElement(item, parent) {
      var element = document.createElement("article");
      element.className = "guide-comment" + (parent ? " guide-reply" : "");
      element.id = "comment-" + item.id;
      var meta = document.createElement("div");
      meta.className = "guide-comment__meta";
      var author = document.createElement("span");
      author.className = "guide-comment__author";
      author.textContent = person(item.author);
      meta.appendChild(author);
      var when = document.createElement("time");
      when.textContent =
        new Date(item.createdAt).toLocaleString() +
        (item.editedAt ? " · edited" : "");
      meta.appendChild(when);
      element.appendChild(meta);
      var body = document.createElement("p");
      body.className = "guide-comment__text";
      body.textContent =
        item.state === "WITHDRAWN" || item.withdrawn
          ? "Withdrawn by the commenter."
          : item.text;
      element.appendChild(body);
      if (!parent) {
        var state = document.createElement("p");
        state.className = "guide-comment__state";
        state.textContent = "State: " + item.state.toLowerCase();
        element.appendChild(state);
        if (item.disposition) {
          var disposition = document.createElement("p");
          disposition.className = "guide-comment__disposition";
          disposition.textContent =
            item.disposition.label + ": " + item.changeNote;
          element.appendChild(disposition);
          var disposed = document.createElement("p");
          disposed.className = "aira-meta";
          disposed.textContent =
            "Disposed by " +
            person(item.disposedBy) +
            " on " +
            new Date(item.disposedAt).toLocaleString();
          element.appendChild(disposed);
        }
        if (item.state === "CLOSED") {
          element.classList.add("guide-comment--closed");
        }
      }
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
              element,
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
              element,
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
              element,
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
              openDispositionForm(element, item);
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
            openReattachForm(element, item);
          });
        }
        if (permissions.canDelete) {
          addTool(tools, "Delete", function () {
            openConfirmation(
              element,
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
        element.appendChild(tools);
      }
      if (!parent) {
        (item.replies || []).forEach(function (reply) {
          element.appendChild(itemElement(reply, item));
        });
      }
      return element;
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
      anchorChoices().forEach(function (block) {
        var option = document.createElement("option");
        option.value = block.dataset.anchor;
        var anchor = document.getElementById(block.dataset.anchor);
        option.textContent =
          (anchor && anchor.textContent.trim().slice(0, 80)) ||
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
        var block = remoteBlocks.filter(function (candidate) {
          return candidate.dataset.anchor === select.value;
        })[0];
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
        Array.prototype.forEach.call(
          content.querySelectorAll(".guide-comment[id^='comment-']"),
          function (node) {
            if (node.querySelector(".guide-comment-form")) {
              openThreads[node.id.slice("comment-".length)] = node;
            }
          },
        );
      }
      Array.prototype.forEach.call(
        content.querySelectorAll(".guide-thread,.guide-orphans"),
        function (node) {
          node.remove();
        },
      );
      pruneRowExtras();
      remoteIndex.textContent = "";
      var orphans = [];
      threads = threads.filter(function (thread) {
        return !thread.deleted;
      });
      threads.forEach(function (thread) {
        if (thread.state === "CLOSED" && !showClosed) {
          return;
        }
        var target = remotePlacement(thread);
        var rendered = openThreads[String(thread.id)] || itemElement(thread, null);
        if (target) {
          threadHolder(target).appendChild(rendered);
        } else {
          orphans.push(thread);
        }
        var entry = document.createElement("li");
        var link = document.createElement("a");
        link.href = "#comment-" + thread.id;
        link.textContent =
          person(thread.author) +
          ": " +
          normalizeRemote(thread.text || "Withdrawn by the commenter.").slice(
            0,
            60,
          );
        entry.appendChild(link);
        remoteIndex.appendChild(entry);
      });
      if (orphans.length) {
        var group = document.createElement("section");
        group.className = "guide-orphans";
        var heading = document.createElement("h2");
        heading.textContent = "Orphaned comments";
        group.appendChild(heading);
        orphans.forEach(function (thread) {
          var holder = document.createElement("div");
          holder.className = "guide-thread";
          holder.appendChild(
            openThreads[String(thread.id)] || itemElement(thread, null),
          );
          group.appendChild(holder);
        });
        content.appendChild(group);
      }
      count.textContent = String(threads.length);
      renderReviewFlags();
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

    function openFlagForm(block) {
      var existing = flagFor(block.dataset.anchor);
      openRemoteForm(
        block,
        existing ? "Save review flag" : "Flag for review",
        function (note) {
          return store.flag(block.dataset.anchor, note).then(function (flag) {
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
        { draft: "flag:" + block.dataset.anchor, maxLength: 500 },
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
          renderRemote();
        })
        .catch(showStatusError);
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
      var meta = document.createElement("p");
      meta.className = "aira-meta";
      var stamp = flag.updatedAt || flag.createdAt;
      meta.textContent =
        "Flagged for review by " +
        person(flag.createdBy) +
        (stamp ? ", " + new Date(stamp).toLocaleString() : "");
      popover.appendChild(meta);
      if (documentInfo && documentInfo.permissions.isAuthor) {
        var tools = document.createElement("div");
        tools.className = "guide-comment__tools";
        addTool(tools, "Edit", function () {
          setOpen(false);
          openFlagForm(block);
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
        if (event.key === "Escape") {
          setOpen(false);
          badge.focus();
        }
      });
      if (openFlagAnchor === flag.anchor) {
        setOpen(true);
      }
      return marker;
    }

    function renderReviewFlags() {
      Array.prototype.forEach.call(
        content.querySelectorAll(".guide-flag-marker,.guide-flag-button"),
        function (node) {
          node.remove();
        },
      );
      remoteBlocks.forEach(function (block) {
        block.classList.remove(
          "guide-review-flagged",
          "guide-review-flagged--continued",
        );
      });
      var first = remoteIndex.firstChild;
      if (reviewFlags.length) {
        var heading = document.createElement("li");
        heading.className = "guide-review-flag-heading";
        heading.textContent = "Review flags (" + reviewFlags.length + ")";
        remoteIndex.insertBefore(heading, first);
      }
      reviewFlags.forEach(function (flag) {
        var area = remoteBlocks.filter(function (block) {
          return block.dataset.anchor === flag.anchor;
        });
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
        var entry = document.createElement("li");
        entry.className = "guide-review-flag-entry";
        var link = document.createElement("a");
        link.href = "#" + flag.anchor;
        link.textContent = flag.note;
        entry.appendChild(link);
        if (documentInfo && documentInfo.permissions.isAuthor) {
          var tools = document.createElement("span");
          tools.className = "guide-comment__tools";
          addTool(tools, "Clear", function () {
            clearReviewFlag(flag);
          });
          entry.appendChild(tools);
        }
        remoteIndex.insertBefore(entry, first);
      });
      if (documentInfo && documentInfo.permissions.isAuthor) {
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
            openFlagForm(block);
          });
          controlHost(block).appendChild(button);
        });
      }
      markFlaggedNav();
    }

    function renderIdentity(message) {
      status.textContent = "";
      remoteToggle.hidden = !validAuth();
      if (message) {
        var note = document.createElement("p");
        note.className = "guide-form-error";
        note.textContent = message;
        status.appendChild(note);
      }
      if (!validAuth()) {
        remoteBlocks.forEach(function (block) {
          var button = controlHost(block).querySelector(":scope > .guide-comment-button");
          if (button) {
            button.hidden = true;
          }
        });
        var signIn = document.createElement("button");
        signIn.type = "button";
        signIn.className =
          "aira-button aira-button--primary aira-button--small";
        signIn.textContent = "Sign in to comment";
        signIn.addEventListener("click", function () {
          beginSignIn(false);
        });
        status.appendChild(signIn);
        return;
      }
      remoteBlocks.forEach(function (block) {
        var button = controlHost(block).querySelector(":scope > .guide-comment-button");
        if (button) {
          button.hidden = !(
            documentInfo &&
            documentInfo.isActive &&
            documentInfo.permissions.canComment
          );
        }
      });
      var identity = document.createElement("p");
      identity.className = "aira-meta";
      identity.textContent = "Signed in as " + person(auth.user);
      status.appendChild(identity);
      var actions = document.createElement("div");
      actions.className = "guide-comment-actions";
      var closedLabel = document.createElement("label");
      var closedToggle = document.createElement("input");
      closedToggle.type = "checkbox";
      closedToggle.checked = showClosed;
      closedToggle.addEventListener("change", function () {
        showClosed = closedToggle.checked;
        store
          .load()
          .then(function () {
            renderRemote();
            restartPolling();
          })
          .catch(showStatusError);
      });
      closedLabel.appendChild(closedToggle);
      closedLabel.appendChild(document.createTextNode(" Show closed"));
      actions.appendChild(closedLabel);
      var signOut = document.createElement("button");
      signOut.type = "button";
      signOut.className =
        "aira-button aira-button--secondary aira-button--small";
      signOut.textContent = "Sign out";
      signOut.addEventListener("click", function () {
        revoke(false);
      });
      actions.appendChild(signOut);
      var switchUser = document.createElement("button");
      switchUser.type = "button";
      switchUser.className =
        "aira-button aira-button--ghost aira-button--small";
      switchUser.textContent = "Not you?";
      switchUser.addEventListener("click", function () {
        revoke(true);
      });
      actions.appendChild(switchUser);
      status.appendChild(actions);
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
          renderRemote();
          renderIdentity();
          if (switchAccount) {
            beginSignIn(true);
          }
        });
    }

    function acknowledged() {
      var key = noticePrefix + auth.user.userId;
      if (window.localStorage.getItem(key)) {
        return true;
      }
      return false;
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
      var submit = document.createElement("button");
      submit.type = "submit";
      submit.className = "aira-button aira-button--primary aira-button--small";
      submit.textContent = label;
      form.appendChild(submit);
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
            if (thread) {
              acceptThread(thread);
            }
            form.remove();
          })
          .catch(function (failure) {
            submit.disabled = false;
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
          "/comments?since=" +
          encodeURIComponent(serverTime),
      )
        .then(function (result) {
          serverTime = result.serverTime;
          reviewFlags = result.reviewFlags || [];
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
      if (item) {
        item.classList.add("guide-comment--target");
        item.scrollIntoView({ block: "center" });
      }
    }

    remoteBlocks.forEach(function (block) {
      block.classList.add("guide-block");
      var button = document.createElement("button");
      button.type = "button";
      button.className = "guide-comment-button";
      button.textContent = "\u{1F4AC}";
      button.setAttribute("aria-label", "Comment on this paragraph");
      button.addEventListener("click", function () {
        if (
          documentInfo &&
          documentInfo.isActive &&
          documentInfo.permissions.canComment
        ) {
          openRemoteForm(
            block,
            "Add comment",
            function (text) {
              return store.add(block, text);
            },
            "",
            true,
            { draft: "add:" + block.dataset.anchor },
          );
        }
      });
      controlHost(block).appendChild(button);
    });
    remoteToggle.addEventListener("click", function () {
      var hidden = document.body.classList.toggle("guide-comments-hidden");
      remoteToggle.textContent = hidden ? "Show comments" : "Hide comments";
      remoteToggle.setAttribute("aria-pressed", hidden ? "false" : "true");
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
