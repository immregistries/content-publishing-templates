# Process

## 1. Define the project goal and boundary

Each project has one primary goal and one bounded body of knowledge. State what
the project is intended to establish, what subject it owns, and what falls
outside its responsibility.

The boundary is tested by the core-document rule:

> If substantive material belongs to the project, it must have a defensible
> place in the complete core document: its main text, an appendix, a footnote,
> or its referenced evidence.

Material that cannot meet that test may be delivery context for a particular
product, or it may belong to another project.

## 2. Develop the canonical source and core document

Capture the durable substance in Markdown before optimizing it for a specific
deliverable. The Markdown files, citations, assets, and build configuration
collectively form the canonical source and must build one complete core
document. The core document may contain an executive summary, chapters,
appendices, footnotes, and referenced evidence.

Canonical source may include:

- propositions and recommendations;
- supporting claims and reasoning;
- evidence and citations;
- examples and stories;
- definitions and approved terminology;
- diagrams or descriptions of needed visuals;
- decisions, uncertainties, and open questions;
- audience concerns and likely objections.

Reusable content modules may be introduced when they improve maintenance, but
they remain parts of the core document. They must not become a parallel bucket
of substantive knowledge that the core document does not contain.

## 3. Establish source status

Authors and subject-matter reviewers determine whether material is:

- **Draft:** being developed and not safe to reuse without review;
- **Reviewed:** substantively checked but not necessarily approved for public
  release;
- **Approved:** available for assembly into products within its stated scope;
- **Deprecated:** retained for history but not available for new products.

Status applies to substance, not just wording. A polished paragraph can still
contain an unapproved claim.

## 4. Build and identify a core release

A core release is a named or numbered version of the canonical source that
successfully builds the complete core document. Early examples may be `v0.3`,
`v0.9-rc1`, and `v1.0`.

The release record should identify:

- the canonical-source revision;
- the core-document version;
- generated release artifacts;
- approval or review status;
- known limitations or unresolved issues.

Word, PDF, and HTML builds are representations of the release, not the source
of truth. Comments and tracked changes received in Word are review inputs. They
must be accepted, rejected, or revised in the Markdown, after which the core
document is rebuilt.

## 5. Define a derived-product brief

Every derived product begins with a written brief. At minimum, it states:

- audience;
- purpose;
- action or understanding sought from the audience;
- format and approximate length;
- expected presentation or reading time;
- assumed audience knowledge;
- messages to emphasize;
- material to exclude or de-emphasize;
- tone;
- applicable organizational template;
- the core release and canonical-source files the product may use;
- any delivery context that may be added without changing the core substance.

The brief is the principal human instruction to the assembly process. A vague
brief should produce a request for clarification or an explicitly labeled
assumption, not silent invention.

## 6. Create and approve the outline

Before producing polished prose or slides, assemble an outline that shows:

- the proposed narrative sequence;
- the main point of each section, page, or slide;
- the source modules supporting each point;
- any requested audience action;
- gaps that require changes to canonical source;
- delivery context that belongs only to this product.

Review the outline for argument and scope. This is the least expensive point to
change the product's direction.

## 7. Assemble the derived-product draft

Assembly may select, reorder, summarize, expand, and restate source material to
fit the audience. It must preserve the substance of the source.

The assembly process may create connective language, headings, slide titles,
speaker notes, descriptions of visuals, and product-specific delivery context.
It must flag:

- new factual claims or substantive ideas not present in the core;
- new recommendations or commitments;
- unsupported numbers;
- changed meaning or certainty;
- conflicts among sources;
- sources whose status or currency is unclear.

If a proposed innovation changes the core idea, pause its treatment as merely
product-specific material. Adjudicate it into the canonical Markdown, rebuild
the core release, and then continue the derived product against that release.

For presentations, first produce a content deck: a strong sequence, one main
point per slide, concise supporting material, and useful speaker notes. Visual
polish follows content approval.

## 8. Record traceability

Each product has a manifest identifying:

- its product brief and the core release on which it depends;
- source files used;
- source revision or build date;
- output template and build method;
- deliberate departures from the source;
- unresolved issues;
- reviewers and approval status.

Traceability should be useful without becoming burdensome. File-level sources
are sufficient initially. Claim-level identifiers can be added later if
experience shows that they provide enough value.

## 9. Run checks

Checks should be proportional to the product and may be automated or manual.
They include:

- requested length, format, and audience are reflected;
- every material factual claim has a source;
- citations and links are present and valid where required;
- numbers, dates, names, and terminology agree with the source;
- no deprecated source was used;
- placeholders and unresolved questions are visible;
- required organizational language and accessibility practices are followed;
- generated files open and render correctly;
- the product manifest is current;
- any substantive innovation discovered at the edge has either flowed back to
  canonical source or is visibly awaiting adjudication.

Checks establish consistency and reveal problems; they do not replace editorial
or subject-matter judgment.

## 10. Review and approve

Human review has distinct purposes:

1. **Subject-matter review:** Is it true, supported, and appropriately certain?
2. **Audience review:** Will this audience understand it, and does the sequence
   serve the intended purpose?
3. **Editorial review:** Is it concise, coherent, and consistent?
4. **Publication review:** Is the product authorized for its intended use?

One person may perform several roles, but the questions should remain distinct.

## 11. Render and release

Build the approved source into the final format using the named template.
Generated deliverables should be placed in an output location and should not be
edited as though they were maintained source files.

If an emergency correction is made in PowerPoint, Word, or another output file,
the correction is not authoritative. It must be reconciled into canonical
Markdown or clearly identified delivery context before the next build.

## 12. Feed learning back into the core

After review or use:

- adjudicate factual or conceptual issues in the canonical source;
- make audience-specific improvements in the product source or brief;
- improve templates and checks when the issue is mechanical;
- record genuinely local variations rather than forcing them into common
  content;
- create a new core release when the accepted change warrants it;
- rebuild or review affected derived products against the new release.

Derived products are useful testing surfaces for the core idea. This feedback
step lets innovations at the edges improve the core while preventing several
products from becoming several competing versions of the truth.

## Roles

| Role | Primary responsibility |
| --- | --- |
| Content owner | Accuracy, scope, status, and continued maintenance of canonical source |
| Product requester | Audience, purpose, desired outcome, timing, and constraints |
| Assembler/editor | Selection, narrative structure, adaptation, and gap identification |
| Subject-matter reviewer | Factual accuracy, evidence, and implications |
| Design/template owner | Organizational identity, layouts, and accessibility |
| Publisher/approver | Authorization of the final product for its stated use |

AI may assist several roles, especially assembly and checking, but it does not
own the content or approve publication.

