#!/bin/sh
set -eu

mode="${1:-staged}"
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

secret_regex='OPENAI_API_KEY=|ANTHROPIC_API_KEY=|DEEPSEEK_API_KEY=|GOOGLE_API_KEY=|PUSHOVER_TOKEN=|PUSHOVER_USER=|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{20,}|sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|BEGIN [A-Z ]*PRIVATE KEY|xox[baprs]-[A-Za-z0-9-]{10,}'

say() {
  printf '%s\n' "$*" >&2
}

match_regex() {
  pattern="$1"
  if command -v rg >/dev/null 2>&1; then
    rg -n -I -e "$pattern"
  else
    grep -En "$pattern"
  fi
}

is_sensitive_filename() {
  case "$1" in
    .env.example|*/.env.example)
      return 1
      ;;
    .env|.env.*|*/.env|*/.env.*|*.pem|*.p12|*.pfx|*.key|id_rsa|*/id_rsa|id_ed25519|*/id_ed25519)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

is_excluded_scan_file() {
  case "$1" in
    .env.example|CLAUDE.md|AGENTS.md|scripts/protect-secrets.sh|.githooks/pre-commit|.githooks/pre-push)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

check_staged_files() {
  blocked=0
  tmp_file_list="$(mktemp)"
  git diff --cached --name-only --diff-filter=ACMR > "$tmp_file_list"
  while IFS= read -r file; do
    [ -n "$file" ] || continue
    if is_sensitive_filename "$file"; then
      say "Blocked: refusing to commit sensitive file '$file'."
      blocked=1
    fi
  done < "$tmp_file_list"
  rm -f "$tmp_file_list"
  [ "$blocked" -eq 0 ]
}

check_staged_content() {
  if git diff --cached --no-color --unified=0 \
    | awk '
        /^\+\+\+ b\// {
          file = substr($0, 7)
          skip = (file == ".env.example" || file == "CLAUDE.md" || file == "AGENTS.md" || file == "scripts/protect-secrets.sh" || file == ".githooks/pre-commit" || file == ".githooks/pre-push")
          next
        }
        /^\+[^+]/ && !skip { print substr($0, 2) }
      ' \
    | match_regex "$secret_regex" >/dev/null; then
    say "Blocked: staged changes contain a secret or credential-looking value."
    return 1
  fi
}

check_head_files() {
  blocked=0
  tmp_file_list="$(mktemp)"
  git ls-tree -r --name-only HEAD > "$tmp_file_list"
  while IFS= read -r file; do
    [ -n "$file" ] || continue
    if is_sensitive_filename "$file"; then
      say "Blocked: HEAD still tracks sensitive file '$file'."
      blocked=1
    fi
  done < "$tmp_file_list"
  rm -f "$tmp_file_list"
  [ "$blocked" -eq 0 ]
}

check_head_content() {
  if git grep -n -I -E "$secret_regex" HEAD -- \
    . \
    ':(exclude).env.example' \
    ':(exclude)CLAUDE.md' \
    ':(exclude)AGENTS.md' \
    ':(exclude)scripts/protect-secrets.sh' \
    ':(exclude).githooks/pre-commit' \
    ':(exclude).githooks/pre-push' >/dev/null; then
    say "Blocked: committed files still contain a secret or credential-looking value."
    return 1
  fi
}

case "$mode" in
  staged)
    check_staged_files || exit 1
    check_staged_content || exit 1
    ;;
  head)
    check_head_files || exit 1
    check_head_content || exit 1
    ;;
  *)
    say "Usage: scripts/protect-secrets.sh [staged|head]"
    exit 2
    ;;
esac
