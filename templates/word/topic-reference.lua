--[[
Topic Reference filter for the Word document.

Listed under the project's docx format in _quarto.yml:

    format:
      docx:
        filters:
          - process/templates/word/topic-reference.lua

It does four things, so the Word document matches the web guide:

1. Change markers (<!-- changed v0.5.0[ feedback][ rows=A,B]: note -->) for
   the current version become a one-line italic note above what they cover:
   "Changed in v0.5.0: ...", prefixed "Feedback wanted." for a feedback
   marker. Older markers are dropped. The current version comes from the
   change-version metadata, which build.ps1 passes from
   process/tools/change_markers.py --current-version; without it, every
   marker is shown.
2. The status notice (::: {.status-notice}) takes the "Status Notice"
   paragraph style, a shaded paragraph in the AIRA reference document.
3. "What changed in v0.5.0", every shown marker with its section, feedback
   wanted first, goes just before the Scope heading, so it follows the
   Executive Summary. insert_word_infographic.py then places the infographic
   between it and the Scope.
4. The Scope's In scope and Out of scope lists become a two-column table, with
   Not yet decided as a full-width row beneath when present. build.ps1 then
   gives it the AIRA 2 table style like every other table.
]]

local SUMMARY_ID = "executive-summary"
local SCOPE_ID = "scope"
local SCOPE_PARTS = { ["in scope"] = "in", ["out of scope"] = "out", ["not yet decided"] = "undecided" }

local current = nil

local function version_key(version)
  local parts = {}
  for number in version:sub(2):gmatch("%d+") do
    table.insert(parts, tonumber(number))
  end
  while #parts < 4 do
    table.insert(parts, 0)
  end
  return parts
end

local function shown(version)
  if current == nil or current == "" then
    return true
  end
  local left, right = version_key(version), version_key(current)
  for index = 1, 4 do
    if left[index] ~= right[index] then
      return left[index] > right[index]
    end
  end
  return true
end

-- A change marker in a raw HTML block, or nil. The content check has already
-- rejected malformed markers, so this only needs to read good ones.
local function parse_marker(raw)
  local text = raw:match("^%s*<!%-%-%s*changed%s+(.-)%s*%-%->%s*$")
  if not text then
    return nil
  end
  text = text:gsub("%s+", " ")
  local head, note = text:match("^(.-)%s*:%s*(.*)$")
  if not head then
    return nil
  end
  local version = head:match("^(v[%d%.]+)")
  if not version then
    return nil
  end
  return {
    version = version,
    feedback = head:find("feedback", 1, true) ~= nil,
    rows = head:match("rows=([^%s]+)"),
    note = note,
  }
end

local function note_paragraph(marker)
  local label = "Changed in " .. marker.version
  if marker.rows then
    label = label .. " (" .. marker.rows:gsub(",", ", ") .. ")"
  end
  local inlines = pandoc.Inlines({})
  if marker.feedback then
    inlines:insert(pandoc.Strong(pandoc.Inlines("Feedback wanted.")))
    inlines:insert(pandoc.Space())
  end
  inlines:insert(pandoc.Emph(pandoc.Inlines(label .. ": " .. marker.note)))
  return pandoc.Para(inlines)
end

local function what_changed(entries)
  local versions, seen = {}, {}
  for _, entry in ipairs(entries) do
    if not seen[entry.marker.version] then
      seen[entry.marker.version] = true
      table.insert(versions, entry.marker.version)
    end
  end
  local title = "What changed"
  if #versions == 1 then
    title = title .. " in " .. versions[1]
  end
  local items = {}
  for _, wanted in ipairs({ true, false }) do
    for _, entry in ipairs(entries) do
      if entry.marker.feedback == wanted then
        local inlines = pandoc.Inlines({})
        if entry.section ~= "" then
          inlines:insert(pandoc.Strong(pandoc.Inlines(entry.section .. ":")))
          inlines:insert(pandoc.Space())
        end
        inlines:extend(pandoc.Inlines(entry.marker.note))
        if wanted then
          inlines:insert(pandoc.Space())
          inlines:insert(pandoc.Emph(pandoc.Inlines("(feedback wanted)")))
        end
        table.insert(items, { pandoc.Plain(inlines) })
      end
    end
  end
  return {
    pandoc.Header(1, pandoc.Inlines(title), pandoc.Attr("what-changed")),
    pandoc.BulletList(items),
  }
end

local function cell(blocks, columns)
  return pandoc.Cell(blocks, pandoc.AlignDefault, 1, columns or 1)
end

-- The Scope's lists as a table. parts maps "in", "out", "undecided" to their blocks.
local function scope_table(parts)
  local head = pandoc.TableHead({ pandoc.Row({
    cell({ pandoc.Plain(pandoc.Inlines("In scope")) }),
    cell({ pandoc.Plain(pandoc.Inlines("Out of scope")) }),
  }) })
  local rows = { pandoc.Row({ cell(parts["in"] or {}), cell(parts["out"] or {}) }) }
  if parts["undecided"] then
    local blocks = { pandoc.Para({ pandoc.Strong(pandoc.Inlines("Not yet decided")) }) }
    for _, block in ipairs(parts["undecided"]) do
      table.insert(blocks, block)
    end
    table.insert(rows, pandoc.Row({ cell(blocks, 2) }))
  end
  local body = { attr = pandoc.Attr(), body = rows, head = {}, row_head_columns = 0 }
  return pandoc.Table(
    pandoc.Caption(),
    { { pandoc.AlignDefault, 0.5 }, { pandoc.AlignDefault, 0.5 } },
    head,
    { body },
    pandoc.TableFoot()
  )
end

local function is_marker(block)
  return block.t == "RawBlock" and block.format:match("html") and parse_marker(block.text) ~= nil
end

-- Whether the blocks from index start the next top-level section: its
-- heading, or change markers just before it.
local function next_section_at(source, index)
  while index <= #source and is_marker(source[index]) do
    index = index + 1
  end
  return index <= #source and source[index].t == "Header" and source[index].level == 1
end

function Pandoc(doc)
  current = doc.meta["change-version"] and pandoc.utils.stringify(doc.meta["change-version"]) or nil
  local blocks = pandoc.Blocks({})
  local entries = {}
  local section = ""
  local scope_at = nil
  local index = 1
  local source = doc.blocks
  while index <= #source do
    local block = source[index]
    if block.t == "Header" then
      section = pandoc.utils.stringify(block.content)
      if block.level == 1 and block.identifier == SCOPE_ID then
        scope_at = #blocks + 1
        blocks:insert(block)
        -- Gather the Scope down to the next top-level heading.
        local intro, parts, part = {}, {}, nil
        index = index + 1
        while index <= #source and not next_section_at(source, index) do
          local inner = source[index]
          if inner.t == "Header" and inner.level == 2
              and SCOPE_PARTS[pandoc.utils.stringify(inner.content):lower()] then
            part = SCOPE_PARTS[pandoc.utils.stringify(inner.content):lower()]
            parts[part] = {}
          elseif part then
            table.insert(parts[part], inner)
          else
            table.insert(intro, inner)
          end
          index = index + 1
        end
        for _, block_in_intro in ipairs(intro) do
          blocks:insert(block_in_intro)
        end
        if parts["in"] or parts["out"] then
          blocks:insert(scope_table(parts))
        end
        goto continue
      end
      blocks:insert(block)
    elseif block.t == "RawBlock" and block.format:match("html") and parse_marker(block.text) then
      local marker = parse_marker(block.text)
      if shown(marker.version) then
        -- A marker before a heading belongs to the section it opens.
        local where = section
        local following = source[index + 1]
        if following and following.t == "Header" then
          where = pandoc.utils.stringify(following.content)
        end
        table.insert(entries, { marker = marker, section = where })
        blocks:insert(note_paragraph(marker))
      end
    elseif block.t == "Div" and block.classes:includes("status-notice") then
      block.attributes["custom-style"] = "Status Notice"
      blocks:insert(block)
    else
      blocks:insert(block)
    end
    index = index + 1
    ::continue::
  end
  if #entries > 0 then
    local listing = what_changed(entries)
    local position = scope_at or (#blocks + 1)
    for offset, block in ipairs(listing) do
      blocks:insert(position + offset - 1, block)
    end
  end
  doc.blocks = blocks
  return doc
end
