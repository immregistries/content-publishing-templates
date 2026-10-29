# AIRA Rapid Presentation Template: Build Checklist

## Goal

Create a small, predictable PowerPoint starter deck for rapid meeting
presentations. It should preserve AIRA's visual identity while making content
accuracy and speed more important than elaborate design.

This checklist records how the rapid template in this repository was made, and
how to remake or revise it. The original AIRA presentation template it was
derived from is held by AIRA and is not distributed here; it remains the visual
authority. The controlled derivative is:

```text
../templates/powerpoint/AIRA Rapid Presentation Template.pptx
```

The source template is widescreen 16:9 and uses Open Sans Light for headings,
Open Sans for body text, and the AIRA color palette. It contains 46 layouts
across four masters, many with duplicate names. The rapid template identifies
two supported master families and 18 unambiguous layouts.

The visual system has two dimensions:

- **Color family:** Green or Blue.
- **Treatment:** Light or Dark for Title and Section layouts.

The Light treatment is mostly white with accents from its color family. The
Dark treatment uses the family color as the dominant field with light accents.
These are visual choices and do not encode meaning.

## Before editing

- [ ] Use the desktop version of PowerPoint. PowerPoint for the web cannot edit
      slide masters.
- [ ] Open the original AIRA presentation.
- [ ] Immediately use **File > Save a Copy** and save it as
      `AIRA Rapid Presentation Template.pptx`.
- [ ] Close the original so it cannot be changed accidentally.
- [ ] Confirm **Design > Slide Size** shows widescreen 16:9.
- [ ] Confirm Open Sans and Open Sans Light are installed and displaying
      correctly.

## A quick orientation to Slide Master view

Open **View > Slide Master**. In the left pane:

- the large top thumbnail is a slide master;
- the indented thumbnails beneath it are layouts belonging to that master;
- additional large thumbnails begin additional master families.

Edit recurring branding and global styles on the master. Edit the position and
type of content areas on the individual layouts. PowerPoint calls those content
areas **placeholders**.

Use real placeholders rather than drawing ordinary text boxes. Placeholders
give both people and generation tools predictable locations for titles, body
text, and pictures.

## Recommended construction approach

Because the source contains several master families, do not begin by deleting
everything. First create and test the nine Green layouts and nine Blue layouts
under their corresponding masters. Remove unused masters only after the
specimen slides work correctly.

### 1. Prepare the supported masters

- [ ] In Slide Master view, identify the Green and Blue master families.
- [ ] Preserve each family's background art, theme colors, fonts, logo
      treatment, and footer positions.
- [ ] Confirm the heading theme font is Open Sans Light and the body theme font
      is Open Sans.
- [ ] Decide whether ordinary content slides should show a slide number and
      footer; apply that choice consistently.
- [ ] Hide unnecessary footer elements on title and section layouts.

### 2. Create exactly 18 supported layouts

PowerPoint recommends duplicating the closest existing layout before changing
or removing placeholders. Right-click a layout thumbnail and select
**Duplicate Layout**, then right-click the copy and select **Rename Layout**.

Use these exact visible names.

#### Title variants

- [ ] `Rapid - Title - Green Light`
- [ ] `Rapid - Title - Green Dark`
- [ ] `Rapid - Title - Blue Light`
- [ ] `Rapid - Title - Blue Dark`
- [ ] Keep a centered title placeholder on each.
- [ ] Keep one subtitle placeholder for optional subtitle, presenter, and date.
- [ ] Preserve the appropriate family and treatment background.
- [ ] Do not show a slide number unless AIRA practice requires it.

#### Section variants

- [ ] `Rapid - Section - Green Light`
- [ ] `Rapid - Section - Green Dark`
- [ ] `Rapid - Section - Blue Light`
- [ ] `Rapid - Section - Blue Dark`
- [ ] Keep a large section-title placeholder.
- [ ] Keep one optional subtitle or orienting-sentence placeholder.
- [ ] Make it visually distinct enough to mark a transition without adding
      decorative complexity.

#### Green working layouts

- [ ] `Rapid - Title and Content - Green`
- [ ] `Rapid - Title and Two Content - Green`
- [ ] `Rapid - Comparison - Green`
- [ ] `Rapid - Title Only - Green`
- [ ] `Rapid - Blank - Green`

#### Blue working layouts

- [ ] `Rapid - Title and Content - Blue`
- [ ] `Rapid - Title and Two Content - Blue`
- [ ] `Rapid - Comparison - Blue`
- [ ] `Rapid - Title Only - Blue`
- [ ] `Rapid - Blank - Blue`

#### Working-layout behavior

- [ ] Title and Content has one title and one general content placeholder.
- [ ] Title and Two Content has one title and two general content placeholders;
      either content region can hold an image.
- [ ] Comparison has a slide title, two column headings, and two corresponding
      content placeholders.
- [ ] Title Only has a title placeholder and an otherwise open composition
      area.
- [ ] Blank retains only stable family branding and the agreed footer behavior.
- [ ] Do not add a dedicated image layout. Use Two Content, Title Only, or Blank
      depending on the composition.

To add a missing placeholder, select the layout and use **Slide Master > Insert
Placeholder**, choose its type, and drag its bounds. To move or resize one,
select its border and use the normal move or sizing handles.

## Remove ambiguity

- [ ] Verify that all 18 supported layouts have the exact unique names above.
- [ ] Rename any retained unsupported layouts with an `Archive -` prefix, or
      delete them after testing.
- [ ] Remove unused master families only after no specimen slide depends on
      them.
- [ ] Do not leave alternate layouts with the same `Rapid -` names.
- [ ] Close Slide Master view.

If you edit a layout after applying it to slides, select the affected slides in
Normal view and use **Home > Layout** to reapply that layout. This makes the
slides pick up the revised placeholder arrangement.

## Create specimen slides

Create one normal slide using each of the 18 supported layouts. These are both
a visual catalog and a fallback for generation tools that duplicate slides
instead of creating them from layouts.

- [ ] Create nine consecutive Green specimen slides in the order used in the
      contract file.
- [ ] Create nine consecutive Blue specimen slides in the same role order.
- [ ] Demonstrate Light and Dark treatments on both Title and Section slides.
- [ ] On each Two Content specimen, place text in one side and a sample image in
      the other.
- [ ] On each Comparison specimen, populate both column headings and both
      corresponding content areas.
- [ ] On each Title Only specimen, place a temporary diagram, quotation, or
      large visual below the title.
- [ ] On each Blank specimen, place a temporary sample diagram or shape.
- [ ] Put obvious specimen text on each slide, such as “Layout specimen—not
      presentation content.”
- [ ] Confirm title and body text remain editable.
- [ ] Confirm an inserted picture crops acceptably in both image-capable
      layouts.

## Content limits to test

Use the specimens to establish practical limits rather than relying on
automatic text shrinking.

- [ ] Test a two-line assertion-style title.
- [ ] Test five concise first-level bullets on the standard content layout.
- [ ] Test three bullets in one column of the two-content layout.
- [ ] Confirm no normal body text must fall below 18 points; prefer 20 points or
      larger where the design permits.
- [ ] Confirm titles remain readable at the agreed standard size.
- [ ] Confirm overflow is visible rather than silently producing unreadably
      small text.
- [ ] Record final font sizes and approximate content limits in
      `templates/powerpoint/aira-rapid-presentation.yml`.

## Save the working template

- [ ] Save the controlled starter as
      `../templates/powerpoint/AIRA Rapid Presentation Template.pptx`.
- [ ] Keep the 18 specimen slides in this PPTX. The generator removes them when
      it builds a deck.
- [ ] Optionally save a second `.potx` copy for people who want to create a new
      deck through PowerPoint's template interface. The `.pptx` remains the
      automation baseline.
- [ ] Do not overwrite the original AIRA presentation.
- [ ] Remove author names from the file properties, and use only images that may
      be redistributed publicly, before committing the template here.

## Final validation

- [ ] The rapid template opens without repair warnings.
- [ ] It remains 16:9.
- [ ] Exactly two master families are required by the 18 specimen slides: Green
      and Blue.
- [ ] All 18 supported layouts appear once and have exact names.
- [ ] Each family has nine supported layouts.
- [ ] The AIRA logo, colors, and fonts render correctly.
- [ ] Title, body, and picture placeholders behave as intended.
- [ ] Slide numbers and footers behave consistently.
- [ ] Every specimen slide remains fully editable.
- [ ] The file contains no real meeting content, confidential information, or
      obsolete agenda material.
- [ ] A person can create a new slide and select each supported layout from
      **Home > New Slide** or **Home > Layout**.

## Microsoft references

- [Create and save a PowerPoint template](https://support.microsoft.com/en-US/PowerPoint/create-and-save-a-powerpoint-template)
- [Edit and reapply a slide layout](https://support.microsoft.com/en-us/powerpoint/edit-and-re-apply-a-slide-layout)
- [Add, edit, or remove a placeholder](https://support.microsoft.com/en-gb/powerpoint/add-edit-or-remove-a-placeholder-on-a-slide-layout)
- [Rename a slide layout](https://support.microsoft.com/en-us/powerpoint/rename-a-slide-layout)

