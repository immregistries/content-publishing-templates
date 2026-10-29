$ErrorActionPreference = 'Stop'

$python = Get-Command python -ErrorAction Stop
$fixture = Join-Path $PSScriptRoot 'tests\fixture-project'
$tools = Join-Path $PSScriptRoot 'tools'

& $python.Source -m py_compile `
    (Join-Path $tools 'build_core_markdown.py') `
    (Join-Path $tools 'check_content.py') `
    (Join-Path $tools 'apply_word_table_style.py') `
    (Join-Path $tools 'build_guide.py') `
    (Join-Path $tools 'import_guide_comments.py')
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

Write-Host "Repository validation passed."
