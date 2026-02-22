param(
    [string]$Host = "127.0.0.1",
    [int]$Port = 8000
)

# Local development defaults.
if (-not $env:SECRET_KEY) {
    $env:SECRET_KEY = "dev-only-secret-key-change-me"
}
if (-not $env:DEBUG) {
    $env:DEBUG = "True"
}
if (-not $env:ALLOWED_HOSTS) {
    $env:ALLOWED_HOSTS = "127.0.0.1,localhost,testserver"
}

python manage.py runserver "$Host`:$Port"
