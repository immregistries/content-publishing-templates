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
