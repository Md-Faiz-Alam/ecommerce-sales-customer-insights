<#
.SYNOPSIS
  Project task runner (Windows equivalent of a Makefile).

.EXAMPLE
  .\tasks.ps1 setup      # create .venv and install everything
  .\tasks.ps1 data       # download raw Olist CSVs from Kaggle
  .\tasks.ps1 pipeline   # clean -> validate -> parquet -> DuckDB -> data quality report
  .\tasks.ps1 train      # train ML models -> models/, reports/model_report.md
  .\tasks.ps1 export     # star-schema CSVs for Power BI -> data/powerbi/
  .\tasks.ps1 export-app # refresh the Streamlit app's data + models -> app/
  .\tasks.ps1 app        # run the Streamlit app locally (http://localhost:8501)
  .\tasks.ps1 notebooks  # re-execute analysis notebooks (refreshes reports/figures)
  .\tasks.ps1 test       # run unit tests
  .\tasks.ps1 lint       # ruff lint + format check
  .\tasks.ps1 all        # data + pipeline + test
#>
param([Parameter(Position = 0)][string]$Task = "help")

$ErrorActionPreference = "Stop"
$Py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

function Invoke-Py { & $Py @args; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }

switch ($Task) {
    "setup" {
        if (-not (Test-Path $Py)) { py -3.13 -m venv (Join-Path $PSScriptRoot ".venv") }
        Invoke-Py -m pip install --upgrade pip
        Invoke-Py -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
        Invoke-Py -m pip install -e $PSScriptRoot --no-deps
    }
    "data"     { Invoke-Py (Join-Path $PSScriptRoot "scripts\download_data.py") }
    "pipeline" { Invoke-Py -m ecom.pipeline }
    "train"    { Invoke-Py -m ecom.models.train }
    "export"   { Invoke-Py -m ecom.export_bi }
    "export-app" { Invoke-Py -m ecom.export_app }
    "app"      { Invoke-Py -m streamlit run (Join-Path $PSScriptRoot "app\streamlit_app.py") }
    "notebooks" {
        Get-ChildItem (Join-Path $PSScriptRoot "notebooks\*.ipynb") | ForEach-Object {
            Invoke-Py -m jupyter nbconvert --to notebook --execute --inplace $_.FullName
        }
    }
    "test"     { Invoke-Py -m pytest --cov }
    "lint"     { Invoke-Py -m ruff check src tests scripts app notebooks; Invoke-Py -m ruff format --check src tests scripts app }
    "all"      { & $PSCommandPath data; & $PSCommandPath pipeline; & $PSCommandPath test }
    default    { Get-Help $PSCommandPath -Detailed }
}
