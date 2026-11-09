$ErrorActionPreference = 'Stop'

# Keep Quarto's user cache inside the project so builds also work in restricted
# or service accounts that cannot write to the normal Windows profile cache.
$env:LOCALAPPDATA = Join-Path (Get-Location) '.quarto\local-app-data'
New-Item -ItemType Directory -Force -Path $env:LOCALAPPDATA | Out-Null
# In a workspace kept in a synced folder, ask Dropbox not to sync the cache, and
# keep Python from writing caches beside the shared tools. Harmless elsewhere.
try { Set-Content -LiteralPath .quarto -Stream com.dropbox.ignored -Value 1 -ErrorAction Stop } catch {}
$env:PYTHONDONTWRITEBYTECODE = '1'

if (-not (Test-Path .\process\templates\word\aira-reference-document.docx)) {
    throw "Shared templates are missing from process/. See Build in README.md."
}

$python = Get-Command python -ErrorAction Stop
& $python.Source .\process\tools\build_core_markdown.py --assembly {{ASSEMBLY}}.qmd
if ($LASTEXITCODE -ne 0) {
    throw "Core Markdown generation failed with exit code $LASTEXITCODE."
}

# The primary infographic is drawn first so the Word document and the guide can
# both include it. Drawing it needs an installed Chrome or Edge.
& $python.Source .\process\tools\build_infographic.py
if ($LASTEXITCODE -ne 0) {
    throw "Building the primary infographic failed with exit code $LASTEXITCODE."
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

& $python.Source .\process\tools\insert_word_infographic.py .\output\{{ASSEMBLY}}.docx
if ($LASTEXITCODE -ne 0) {
    throw "Placing the infographic in the Word document failed with exit code $LASTEXITCODE."
}

& $python.Source .\process\tools\build_guide.py --assembly {{ASSEMBLY}}.qmd
if ($LASTEXITCODE -ne 0) {
    throw "Building the web guide failed with exit code $LASTEXITCODE."
}

Write-Host "Built the core document, primary infographic, and web guide in output/. {{BUILD_MESSAGE}}"
