/* Content guide: section tracking and browser-only comments. */
(function () {
  "use strict";

  var data = JSON.parse(document.getElementById("guide-data").textContent);
  var content = document.getElementById("guide-content");
  var sectionLinks = Array.prototype.slice.call(
    document.querySelectorAll(".guide-context .aira-context-nav a")
  );
  var sections = Array.prototype.slice.call(content.querySelectorAll("section.level2"));
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
    var subsections = section ? section.querySelectorAll(":scope > section.level3") : [];
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
  }

  function update() {
    var section = lastAbove(sections);
    if (section !== currentSection) {
      currentSection = section;
      currentSubsection = null;
      sectionLinks.forEach(function (link) {
        if (section && link.getAttribute("href") === "#" + section.id) {
          link.setAttribute("aria-current", "page");
          link.scrollIntoView({ block: "nearest", inline: "nearest" });
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
      section.querySelectorAll(":scope > section.level3")
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
      Array.prototype.forEach.call(subnav.querySelectorAll("a"), function (link) {
        if (sub && link.getAttribute("href") === "#" + sub.id) {
          link.setAttribute("aria-current", "true");
        } else {
          link.removeAttribute("aria-current");
        }
      });
    }
  }

  var pending = false;
  window.addEventListener("scroll", function () {
    if (!pending) {
      pending = true;
      window.requestAnimationFrame(function () {
        pending = false;
        update();
      });
    }
  }, { passive: true });
  window.addEventListener("resize", update);
  update();

  // ---- Comments ----

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
  try {
    comments = JSON.parse(load(STORAGE_KEY) || "[]");
  } catch (error) {
    comments = [];
  }

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
    store(STORAGE_KEY, JSON.stringify(comments));
  }

  function normalize(text) {
    return (text || "").replace(/\s+/g, " ").trim();
  }

  function newId() {
    if (window.crypto && window.crypto.randomUUID) {
      return window.crypto.randomUUID();
    }
    return "c-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 10);
  }

  // Commentable blocks: outermost paragraphs, list items, quotes, tables, code.
  var BLOCK_SELECTOR = "p, li, blockquote, .aira-table-wrap, pre";
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
    }
  );

  var counters = {};
  blocks.forEach(function (block) {
    var section = block.closest("section");
    var sectionId = section ? section.id : "top";
    counters[sectionId] = (counters[sectionId] || 0) + 1;
    block.dataset.guideSection = sectionId;
    block.dataset.guideIndex = String(counters[sectionId]);
    block.dataset.guideText = normalize(block.textContent).slice(0, 160);
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
    block.appendChild(button);
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

  function findBlock(comment) {
    var exact = blocks.filter(function (block) {
      return block.dataset.guideSection === comment.sectionId &&
        block.dataset.guideIndex === String(comment.blockIndex);
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

  function threadFor(block) {
    var next = block.nextElementSibling;
    if (next && next.classList.contains("guide-thread")) {
      return next;
    }
    var thread = document.createElement("div");
    thread.className = "guide-thread";
    block.insertAdjacentElement("afterend", thread);
    return thread;
  }

  function formatTime(iso) {
    try {
      return new Date(iso).toLocaleString([], {
        dateStyle: "medium",
        timeStyle: "short"
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
    when.textContent = formatTime(comment.created) +
      (comment.documentVersion && comment.documentVersion !== data.version
        ? " · on " + comment.documentVersion
        : "");
    var tools = document.createElement("span");
    tools.className = "guide-comment__tools";
    var edit = document.createElement("button");
    edit.type = "button";
    edit.textContent = "Edit";
    edit.addEventListener("click", function () {
      var block = findBlock(comment);
      if (block) {
        openForm(block, comment.quote, comment);
      }
    });
    var remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "Delete";
    remove.addEventListener("click", function () {
      comments = comments.filter(function (other) {
        return other.id !== comment.id;
      });
      save();
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
      }
    );
    index.textContent = "";
    comments.sort(function (a, b) {
      return (a.created || "").localeCompare(b.created || "");
    });
    var unplaced = [];
    comments.forEach(function (comment) {
      var block = findBlock(comment);
      if (block) {
        threadFor(block).appendChild(commentElement(comment));
      } else {
        unplaced.push(comment);
      }
      var entry = document.createElement("li");
      var link = document.createElement("a");
      link.href = block ? "#comment-" + comment.id : "#guide-comments-panel";
      link.textContent = (comment.author || "Anonymous") + ": " +
        normalize(comment.text).slice(0, 60) +
        (normalize(comment.text).length > 60 ? "…" : "");
      entry.appendChild(link);
      var where = document.createElement("span");
      where.className = "aira-meta";
      where.textContent = block
        ? comment.sectionTitle || comment.sectionId
        : "Not placed: the text it refers to has changed";
      entry.appendChild(where);
      index.appendChild(entry);
    });
    countBadge.textContent = String(comments.length);
    if (unplaced.length) {
      unplaced.forEach(function (comment) {
        var holder = document.createElement("div");
        holder.className = "guide-thread";
        holder.appendChild(commentElement(comment));
        index.appendChild(holder);
      });
    }
  }

  function closeForms() {
    Array.prototype.forEach.call(
      content.querySelectorAll(".guide-comment-form"),
      function (form) {
        form.remove();
      }
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
    var label = document.createElement("label");
    label.className = "aira-visually-hidden";
    label.textContent = "Comment";
    var textarea = document.createElement("textarea");
    textarea.className = "aira-textarea";
    textarea.required = true;
    textarea.value = existing ? existing.text : "";
    label.appendChild(textarea);
    form.appendChild(label);

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
        existing.text = text;
        existing.updated = new Date().toISOString();
      } else {
        comments.push({
          id: newId(),
          documentId: data.id,
          documentVersion: data.version,
          sectionId: block.dataset.guideSection,
          sectionTitle: sectionTitle(block),
          blockIndex: Number(block.dataset.guideIndex),
          blockText: block.dataset.guideText,
          quote: quote || "",
          author: author,
          created: new Date().toISOString(),
          text: text
        });
      }
      save();
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

  document.getElementById("guide-comments-download").addEventListener("click", function () {
    var author = nameInput.value.trim() || "comments";
    var payload = {
      format: FORMAT,
      formatVersion: 1,
      documentId: data.id,
      documentTitle: data.title,
      documentVersion: data.version,
      exported: new Date().toISOString(),
      exportedBy: nameInput.value.trim(),
      comments: comments
    };
    var blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    var link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = data.id + "-comments-" +
      author.toLowerCase().replace(/[^a-z0-9]+/g, "-") + "-" +
      new Date().toISOString().slice(0, 10) + ".json";
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(function () {
      URL.revokeObjectURL(link.href);
    }, 1000);
  });

  document.getElementById("guide-comments-load").addEventListener("change", function (event) {
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

  document.getElementById("guide-comments-clear").addEventListener("click", function () {
    if (comments.length && window.confirm(
      "Remove all " + comments.length + " comments from this browser? Download them first if you need them."
    )) {
      comments = [];
      save();
      render();
    }
  });

  render();
})();
