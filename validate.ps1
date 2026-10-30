$ErrorActionPreference = 'Stop'

$python = Get-Command python -ErrorAction Stop
$fixture = Join-Path $PSScriptRoot 'tests\fixture-project'
$tools = Join-Path $PSScriptRoot 'tools'

& $python.Source -m py_compile `
    (Join-Path $tools 'build_core_markdown.py') `
    (Join-Path $tools 'check_content.py') `
    (Join-Path $tools 'apply_word_table_style.py') `
    (Join-Path $tools 'build_guide.py') `
    (Join-Path $tools 'import_guide_comments.py') `
    (Join-Path $tools 'new_topic_reference.py')
if ($LASTEXITCODE -ne 0) {
    throw "Python validation failed."
}

& $python.Source (Join-Path $tools 'build_core_markdown.py') --root $fixture --assembly Example.qmd --check
if ($LASTEXITCODE -ne 0) {
    throw "Fixture reading copy is out of date."
}

& $python.Source (Join-Path $tools 'check_content.py') --root $fixture
if ($LASTEXITCODE -ne 0) {
    throw "Fixture content checks failed."
}

$guide = Join-Path $PSScriptRoot 'output/fixture-guide.html'
& $python.Source (Join-Path $tools 'build_guide.py') --root $fixture --assembly Example.qmd --output $guide --version test
if ($LASTEXITCODE -ne 0) {
    throw "Fixture guide build failed."
}
$guideText = Get-Content -LiteralPath $guide -Raw
if ($guideText -notmatch '<div id="document-start" class="guide-anchor"' -or
    $guideText -notmatch '<div id="fixture-introduction" class="guide-anchor"' -or
    $guideText -notmatch 'data-anchor="fixture-introduction" data-block-index="0"' -or
    $guideText -notmatch 'data-anchor="fixture-introduction" data-block-index="2"') {
    throw "Fixture guide is missing anchor elements or comment block metadata."
}
$readingCopyText = Get-Content -LiteralPath (Join-Path $fixture 'CoreDocument.md') -Raw
if ($readingCopyText -notmatch '<!-- anchor: fixture-introduction -->') {
    throw "Fixture reading copy did not preserve the fenced anchor example."
}
if ($readingCopyText -match "(?m)\r?\n(?:\r?\n){2,}") {
    throw "Fixture reading copy gained consecutive blank lines when anchors were removed."
}
if (($guideText | Select-String -Pattern '<div id="fixture-introduction" class="guide-anchor"' -AllMatches).Matches.Count -ne 1) {
    throw "Fixture guide converted or lost the fenced anchor example."
}

$badFixture = Join-Path $PSScriptRoot 'output/fixture-anchor-checks'
if (Test-Path -LiteralPath $badFixture) {
    Remove-Item -LiteralPath $badFixture -Recurse -Force
}
Copy-Item -LiteralPath $fixture -Destination $badFixture -Recurse
Add-Content -LiteralPath (Join-Path $badFixture 'content/01-detail.md') -Value "`n<!-- anchor: fixture-introduction -->`n<!-- anchor: Bad Anchor -->`n<!-- anchor: document-start -->"
$badCheck = & $python.Source (Join-Path $tools 'check_content.py') --root $badFixture 2>&1
if ($LASTEXITCODE -eq 0 -or
    ($badCheck -join "`n") -notmatch 'duplicate anchor' -or
    ($badCheck -join "`n") -notmatch 'malformed anchor syntax' -or
    ($badCheck -join "`n") -notmatch 'is reserved') {
    throw "Content checks did not reject duplicate, malformed, and reserved anchors."
}

$idFixture = Join-Path $PSScriptRoot 'output/fixture-id-check'
if (Test-Path -LiteralPath $idFixture) {
    Remove-Item -LiteralPath $idFixture -Recurse -Force
}
Copy-Item -LiteralPath $fixture -Destination $idFixture -Recurse
Add-Content -LiteralPath (Join-Path $idFixture 'content/01-detail.md') -Value "`n## 3. Dogs`n`n<!-- anchor: dogs -->`n`nCollision fixture."
$idGuide = Join-Path $idFixture 'output/guide/index.html'
$savedErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
$idBuild = & $python.Source (Join-Path $tools 'build_guide.py') --root $idFixture --assembly Example.qmd --output $idGuide --version test 2>&1
$ErrorActionPreference = $savedErrorActionPreference
if ($LASTEXITCODE -eq 0 -or
    ($idBuild -join "`n") -notmatch "duplicate id value.*dogs" -or
    ($idBuild -join "`n") -notmatch "Give one heading a unique explicit ID" -or
    ($idBuild -join "`n") -notmatch "heading ID is also an anchor name") {
    throw "Guide build did not reject an anchor colliding with pandoc's heading ID."
}

$topicReference = Join-Path $PSScriptRoot 'output/topic-reference-test'
if (Test-Path $topicReference) {
    Remove-Item -Recurse -Force $topicReference
}
& $python.Source (Join-Path $tools 'new_topic_reference.py') $topicReference --no-git `
    --title 'Test Topic' --topic 7 --topic-name 'Test Topic' --with presentation
if ($LASTEXITCODE -ne 0) {
    throw "Creating a Topic Reference from the skeleton failed."
}
& $python.Source (Join-Path $tools 'build_core_markdown.py') --root $topicReference --assembly TopicReferenceTest.qmd --check
if ($LASTEXITCODE -ne 0) {
    throw "The new Topic Reference's reading copy is out of date."
}
& $python.Source (Join-Path $tools 'check_content.py') --root $topicReference --include 'LICENSE-CONTENT.md' --include 'CODE_OF_CONDUCT.md'
if ($LASTEXITCODE -ne 0) {
    throw "The new Topic Reference's content checks failed."
}
& $python.Source (Join-Path $tools 'build_guide.py') --root $topicReference --assembly TopicReferenceTest.qmd `
    --output (Join-Path $topicReference 'output/guide/index.html') --version test
if ($LASTEXITCODE -ne 0) {
    throw "The new Topic Reference's guide build failed."
}

& $python.Source -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('pptx') else 1)"
if ($LASTEXITCODE -eq 0) {
    & $python.Source (Join-Path $tools 'build_rapid_presentation.py') `
        --template (Join-Path $PSScriptRoot 'templates/powerpoint/AIRA Rapid Presentation Template.pptx') `
        --source (Join-Path $PSScriptRoot 'templates/powerpoint/example-slides.json') `
        --output (Join-Path $PSScriptRoot 'output/example-deck.pptx')
    if ($LASTEXITCODE -ne 0) {
        throw "Example PowerPoint build failed."
    }
} else {
    Write-Host "python-pptx not installed; skipping the PowerPoint check."
}

Write-Host "Repository validation passed."
