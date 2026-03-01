#!/bin/bash
set -e

# Move to project root
cd "$(dirname "$0")/.."

case "$1" in
  extract)
    echo "Extracting messages..."
    uv run pybabel extract -F babel.cfg -o factfeed/translations/messages.pot .
    ;;
  init)
    if [ -z "$2" ]; then
      echo "Usage: $0 init <locale>"
      exit 1
    fi
    echo "Initializing locale $2..."
    uv run pybabel init -i factfeed/translations/messages.pot -d factfeed/translations -l "$2"
    ;;
  update)
    echo "Updating catalogs..."
    uv run pybabel update -i factfeed/translations/messages.pot -d factfeed/translations
    ;;
  compile)
    echo "Compiling catalogs..."
    uv run pybabel compile -d factfeed/translations
    ;;
  *)
    echo "Usage: $0 {extract|init|update|compile}"
    exit 1
    ;;
esac
