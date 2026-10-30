$ErrorActionPreference = 'Stop'

$python = '.\.venv-pptx\Scripts\python.exe'
if (-not (Test-Path $python)) {
    throw "PowerPoint environment is missing. Run setup-presentation.ps1 first."
}

& $python .\process\tools\build_rapid_presentation.py `
    --template '.\process\templates\powerpoint\AIRA Rapid Presentation Template.pptx' `
    --source '.\products\presentation\slides.json' `
    --output '.\output\{{ID}}-review.pptx'

if ($LASTEXITCODE -ne 0) {
    throw "PowerPoint generation failed with exit code $LASTEXITCODE."
}

Write-Host "Built output/{{ID}}-review.pptx."
