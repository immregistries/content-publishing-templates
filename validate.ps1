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
    (Join-Path $tools 'new_topic_reference.py') `
    (Join-Path $tools 'workspace_process.py') `
    (Join-Path $tools 'check_products.py') `
    (Join-Path $tools 'build_rapid_presentation.py') `
    (Join-Path $tools 'rapid_patterns.py') `
    (Join-Path $tools 'infographic.py') `
    (Join-Path $tools 'headless_browser.py') `
    (Join-Path $tools 'build_infographic.py') `
    (Join-Path $tools 'insert_word_infographic.py')
if ($LASTEXITCODE -ne 0) {
    throw "Python validation failed."
}

& $python.Source -m unittest discover -s (Join-Path $PSScriptRoot 'tests') -p 'test_*.py'
if ($LASTEXITCODE -ne 0) {
    throw "Unit tests failed."
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
if ($readingCopyText -notmatch '(?m)^```mermaid\r?$' -or $readingCopyText -match '```\{mermaid\}') {
    throw "Fixture reading copy did not write the Mermaid fence in the form GitHub draws."
}
if ($guideText -notmatch '<div class="guide-diagram" data-anchor="review-item"' -or
    $guideText -notmatch 'window\.guideDiagramsReady') {
    throw "Fixture guide is missing its Mermaid diagram or the diagram library."
}
if ($guideText -notmatch '<tr id="fx-1" class="guide-row-block" data-guide-anchor="fx-1" data-anchor="fx-1" data-block-index="0">' -or
    $guideText -notmatch '<tr id="fx-2" class="guide-row-block" data-guide-anchor="fx-2" data-anchor="fx-2" data-block-index="0">' -or
    $guideText -notmatch '<div class="aira-table-wrap guide-row-table"><table' -or
    $guideText -notmatch '<p data-anchor="review-item" data-block-index="\d+">Text after the table' -or
    $readingCopyText -match 'row-anchors') {
    throw "Fixture guide did not make each row of the row-anchored table its own review area."
}

$remoteFixture = Join-Path $PSScriptRoot 'output/fixture-remote'
if (Test-Path -LiteralPath $remoteFixture) { Remove-Item -LiteralPath $remoteFixture -Recurse -Force }
Copy-Item -LiteralPath $fixture -Destination $remoteFixture -Recurse
$remoteConfig = Get-Content -LiteralPath (Join-Path $remoteFixture 'guide.json') -Raw | ConvertFrom-Json
$remoteConfig | Add-Member -NotePropertyName comments -NotePropertyValue ([pscustomobject]@{
    mode = 'interophub'; hub = 'http://127.0.0.1:8766/'; document = 'example-core-document'
})
$remoteConfig | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $remoteFixture 'guide.json') -Encoding utf8
$remoteGuide = Join-Path $remoteFixture 'output/guide/index.html'
& $python.Source (Join-Path $tools 'build_guide.py') --root $remoteFixture --assembly Example.qmd --output $remoteGuide --version test
if ($LASTEXITCODE -ne 0) { throw "Fixture guide build in remote comment mode failed." }
$remoteGuideText = Get-Content -LiteralPath $remoteGuide -Raw
if ($remoteGuideText -notmatch '"mode": "interophub"' -or $remoteGuideText -notmatch '"hub": "http://127.0.0.1:8766"') {
    throw "Remote comments settings were not normalized into guide-data."
}

$browser = Get-Command chrome, msedge, chrome.exe, msedge.exe -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $browser) {
    $knownBrowsers = @(
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
        "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
    )
    $browserPath = $knownBrowsers | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
} else { $browserPath = $browser.Source }
if ($browserPath) {
    & $python.Source (Join-Path $PSScriptRoot 'tests/browser_check.py') --browser $browserPath --root $remoteFixture
    if ($LASTEXITCODE -ne 0) { throw "Headless browser comments check failed." }
} else {
    Write-Host "Chrome or Edge not installed; skipping the headless comments check."
}

$badFixture = Join-Path $PSScriptRoot 'output/fixture-anchor-checks'
if (Test-Path -LiteralPath $badFixture) {
    Remove-Item -LiteralPath $badFixture -Recurse -Force
}
Copy-Item -LiteralPath $fixture -Destination $badFixture -Recurse
Add-Content -LiteralPath (Join-Path $badFixture 'content/01-detail.md') -Value "`n<!-- anchor: fixture-introduction -->`n<!-- anchor: Bad Anchor -->`n<!-- anchor: document-start -->`n`n<!-- row-anchors -->`n`n| ID |`n|---|`n| Review item |`n`n<!-- row-anchor -->`n`n<!-- row-anchors -->`n`nNo table follows."
$badCheck = & $python.Source (Join-Path $tools 'check_content.py') --root $badFixture 2>&1
if ($LASTEXITCODE -eq 0 -or
    ($badCheck -join "`n") -notmatch 'duplicate row anchor' -or
    ($badCheck -join "`n") -notmatch 'malformed row-anchors syntax' -or
    ($badCheck -join "`n") -notmatch 'must be followed by a pipe table' -or
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
& $python.Source (Join-Path $tools 'new_topic_reference.py') $topicReference --no-git --visibility public `
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
if ((Get-Content -LiteralPath (Join-Path $topicReference 'output/guide/index.html') -Raw) -notmatch '<figure class="guide-infographic"') {
    throw "The new Topic Reference's guide is missing its primary infographic."
}
if ($browserPath) {
    & $python.Source (Join-Path $tools 'build_infographic.py') --root $topicReference --version test --browser $browserPath
    if ($LASTEXITCODE -ne 0) {
        throw "The new Topic Reference's primary infographic failed to build."
    }
    foreach ($suffix in 'svg', 'png', 'pdf') {
        if (-not (Test-Path -LiteralPath (Join-Path $topicReference "output/infographic.$suffix"))) {
            throw "The new Topic Reference's primary infographic has no $suffix output."
        }
    }
} else {
    Write-Host "Chrome or Edge not installed; skipping the primary infographic export."
}

$privateReference = Join-Path $PSScriptRoot 'output/private-topic-reference-test'
if (Test-Path $privateReference) {
    Remove-Item -Recurse -Force $privateReference
}
& $python.Source (Join-Path $tools 'new_topic_reference.py') $privateReference --no-git --visibility private `
    --owner example-org --title 'Private Test Topic' --topic 8 --topic-name 'Private Test Topic'
if ($LASTEXITCODE -ne 0) {
    throw "Creating a private Topic Reference from the skeleton failed."
}
& $python.Source (Join-Path $tools 'build_core_markdown.py') --root $privateReference --assembly PrivateTopicReferenceTest.qmd --check
if ($LASTEXITCODE -ne 0) {
    throw "The private Topic Reference's reading copy is out of date."
}
& $python.Source (Join-Path $tools 'check_content.py') --root $privateReference --include 'INTERNAL-USE.md'
if ($LASTEXITCODE -ne 0) {
    throw "The private Topic Reference's content checks failed."
}
& $python.Source (Join-Path $tools 'build_guide.py') --root $privateReference --assembly PrivateTopicReferenceTest.qmd `
    --output (Join-Path $privateReference 'output/guide/index.html') --version test
if ($LASTEXITCODE -ne 0) {
    throw "The private Topic Reference's guide build failed."
}
$privateGuide = Get-Content -LiteralPath (Join-Path $privateReference 'output/guide/index.html') -Raw
if ($privateGuide -notmatch '<figure class="guide-infographic"' -or $privateGuide -notmatch 'AIRA internal use only') {
    throw "The private Topic Reference's guide is missing its primary infographic or its internal-use notice."
}
if (Test-Path (Join-Path $privateReference '.github/workflows/publish-guide.yml')) {
    throw "The private Topic Reference has a publishing workflow."
}

$workspaceReference = Join-Path $PSScriptRoot 'output/Workspace Test'
if (Test-Path $workspaceReference) {
    Remove-Item -Recurse -Force $workspaceReference
}
& $python.Source (Join-Path $tools 'new_topic_reference.py') $workspaceReference --no-git --type workspace `
    --id workspace-test --title 'Workspace Test' --location 'Team Dropbox/Ideas/Workspace Test'
if ($LASTEXITCODE -ne 0) {
    throw "Creating a Workspace Topic Reference from the skeleton failed."
}
& $python.Source (Join-Path $tools 'check_content.py') --root $workspaceReference
if ($LASTEXITCODE -ne 0) {
    throw "The Workspace Topic Reference's content checks failed."
}
& $python.Source (Join-Path $tools 'build_guide.py') --root $workspaceReference --assembly WorkspaceTest.qmd `
    --output (Join-Path $workspaceReference 'output/guide/index.html')
if ($LASTEXITCODE -ne 0) {
    throw "The Workspace Topic Reference's guide build failed."
}
if ((Get-Content -LiteralPath (Join-Path $workspaceReference 'output/guide/index.html') -Raw) -notmatch 'Workspace build \d{4}-\d{2}-\d{2}') {
    throw "The Workspace Topic Reference's guide does not show its build date."
}

& $python.Source -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('pptx') else 1)"
if ($LASTEXITCODE -eq 0) {
    & $python.Source (Join-Path $tools 'build_rapid_presentation.py') `
        --template (Join-Path $PSScriptRoot 'templates/powerpoint/AIRA Rapid Presentation Template.pptx') `
        --source (Join-Path $PSScriptRoot 'templates/powerpoint/example-slides.json') `
        --root $fixture `
        --output (Join-Path $PSScriptRoot 'output/example-deck.pptx')
    if ($LASTEXITCODE -ne 0) {
        throw "Example PowerPoint build failed."
    }
    $savedErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $patternBuild = & $python.Source (Join-Path $tools 'build_rapid_presentation.py') `
        --template (Join-Path $PSScriptRoot 'templates/powerpoint/AIRA Rapid Presentation Template.pptx') `
        --source (Join-Path $PSScriptRoot 'templates/powerpoint/example-patterns.json') `
        --root $fixture `
        --output (Join-Path $PSScriptRoot 'output/example-patterns.pptx') 2>&1
    $ErrorActionPreference = $savedErrorActionPreference
    if ($LASTEXITCODE -ne 0 -or ($patternBuild -join "`n") -match 'warning:') {
        throw "Example pattern deck build failed or warned:`n$($patternBuild -join "`n")"
    }
    & $python.Source (Join-Path $tools 'build_rapid_presentation.py') `
        --template (Join-Path $PSScriptRoot 'templates/powerpoint/AIRA Rapid Presentation Template.pptx') `
        --source (Join-Path $topicReference 'products/presentation/slides.json') `
        --root $topicReference `
        --output (Join-Path $topicReference 'output/starter-deck.pptx')
    if ($LASTEXITCODE -ne 0) {
        throw "The new Topic Reference's starter deck failed to build."
    }
    $missingFixture = Join-Path $PSScriptRoot 'output/missing-source.json'
    '{"core_release": "v0", "slides": [{"layout": "Rapid - Blank - Green", "content": [], "speaker_notes": "", "sources": ["content/missing.md"]}]}' |
        Set-Content -LiteralPath $missingFixture -Encoding ascii
    $savedErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $missingBuild = & $python.Source (Join-Path $tools 'build_rapid_presentation.py') `
        --template (Join-Path $PSScriptRoot 'templates/powerpoint/AIRA Rapid Presentation Template.pptx') `
        --source $missingFixture --root $fixture `
        --output (Join-Path $PSScriptRoot 'output/missing-source.pptx') 2>&1
    $ErrorActionPreference = $savedErrorActionPreference
    if ($LASTEXITCODE -eq 0 -or ($missingBuild -join "`n") -notmatch 'content/missing.md') {
        throw "The PowerPoint generator did not reject a missing slide source."
    }
} else {
    Write-Host "python-pptx not installed; skipping the PowerPoint check."
}

Write-Host "Repository validation passed."
