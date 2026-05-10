param (
    [string]$Message = "auto commit"
)

python -m ruff format .
python -m ruff check . --fix

git add -A

git commit -m "$Message"