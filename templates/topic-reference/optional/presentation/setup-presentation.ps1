$ErrorActionPreference = 'Stop'

if (-not (Test-Path .\.venv-pptx\Scripts\python.exe)) {
    $python = Get-Command python -ErrorAction Stop
    & $python.Source -m venv .venv-pptx
    if ($LASTEXITCODE -ne 0) {
        throw "Creating the PowerPoint environment failed."
    }
}

& .\.venv-pptx\Scripts\python.exe -m pip install -r .\process\requirements-pptx.txt
if ($LASTEXITCODE -ne 0) {
    throw "Installing PowerPoint dependencies failed."
}

Write-Host "PowerPoint environment is ready."
