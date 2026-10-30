$ErrorActionPreference = 'Stop'

# Keep Quarto's user cache inside the project so builds also work in restricted
# or service accounts that cannot write to the normal Windows profile cache.
$env:LOCALAPPDATA = Join-Path (Get-Location) '.quarto\local-app-data'
New-Item -ItemType Directory -Force -Path $env:LOCALAPPDATA | Out-Null

if (-not (Test-Path .\process\templates\word\aira-reference-document.docx)) {
    throw "Shared templates are missing. Run: git submodule update --init"
}

$python = Get-Command python -ErrorAction Stop
& $python.Source .\process\tools\build_core_markdown.py --assembly {{ASSEMBLY}}.qmd
if ($LASTEXITCODE -ne 0) {
    throw "Core Markdown generation failed with exit code $LASTEXITCODE."
}

$quarto = Get-Command quarto -ErrorAction Stop
& $quarto.Source render
if ($LASTEXITCODE -ne 0) {
    throw "Quarto build failed with exit code $LASTEXITCODE."
}

& $python.Source .\process\tools\apply_word_table_style.py .\output\{{ASSEMBLY}}.docx
if ($LASTEXITCODE -ne 0) {
    throw "Applying the Word table style failed with exit code $LASTEXITCODE."
}

& $python.Source .\process\tools\build_guide.py --assembly {{ASSEMBLY}}.qmd
if ($LASTEXITCODE -ne 0) {
    throw "Building the web guide failed with exit code $LASTEXITCODE."
}

Write-Host "Built core document and web guide in output/. The published page is output/guide/index.html."
