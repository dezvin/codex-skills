#!/usr/bin/env bash
set -euo pipefail

json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

json_success() {
  printf '{"status":"success","operation":"%s"%s}\n' "$(json_escape "$1")" "$2"
}

json_error() {
  printf '{"status":"error","operation":"%s","message":"%s","next_valid_actions":["inspect-arguments","retry-after-fix"]}\n' "$(json_escape "${1:-unknown}")" "$(json_escape "$2")"
}

die() {
  json_error "${OPERATION:-unknown}" "$1"
  exit 1
}

is_abs() {
  [[ "${1:-}" == /* ]]
}

assert_abs() {
  local path="$1"
  local name="$2"
  is_abs "$path" || die "$name must be an absolute path: $path"
}

candidate_for() {
  local target="$1"
  local dir="${target%/*}"
  local leaf="${target##*/}"
  if [[ "$leaf" == *.* && "$leaf" != .* ]]; then
    local stem="${leaf%.*}"
    local ext=".${leaf##*.}"
    printf '%s/%s.candidate%s' "$dir" "$stem" "$ext"
  else
    printf '%s/%s.candidate' "$dir" "$leaf"
  fi
}

new_backup_dir() {
  local base_dir="$1"
  local root="$base_dir/_backup"
  mkdir -p "$root"
  local stamp
  stamp="$(date '+%Y-%m-%d_%H-%M')"
  local candidate="$root/$stamp"
  local i=2
  while [[ -e "$candidate" ]]; do
    candidate="$root/$stamp-$i"
    i=$((i + 1))
  done
  mkdir -p "$candidate"
  printf '%s' "$candidate"
}

replace_with_candidate() {
  local target=""
  local candidate=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --target) target="${2:-}"; shift 2 ;;
      --candidate) candidate="${2:-}"; shift 2 ;;
      *) die "Unknown argument: $1" ;;
    esac
  done

  [[ -n "$target" ]] || die "--target is required"
  [[ -n "$candidate" ]] || die "--candidate is required"
  assert_abs "$target" "--target"
  assert_abs "$candidate" "--candidate"
  [[ -f "$target" ]] || die "Target not found: $target"
  [[ -f "$candidate" ]] || die "Candidate not found: $candidate"

  local expected
  expected="$(candidate_for "$target")"
  [[ "$candidate" == "$expected" ]] || die "Candidate must be beside target and named as candidate: expected $expected"
  [[ -s "$candidate" ]] || die "Candidate is empty: $candidate"

  local target_dir="${target%/*}"
  local leaf="${target##*/}"
  local backup_dir
  backup_dir="$(new_backup_dir "$target_dir")"
  local backup_target="$backup_dir/$leaf"
  local moved_target="false"

  if mv "$target" "$backup_target"; then
    moved_target="true"
  else
    die "Failed to move target to backup"
  fi

  if mv "$candidate" "$target"; then
    printf '{"status":"success","operation":"replace-with-candidate","target":"%s","candidate":"%s","backup_path":"%s","backup_dir":"%s","moved":[{"from":"%s","to":"%s"},{"from":"%s","to":"%s"}]}\n' \
      "$(json_escape "$target")" "$(json_escape "$candidate")" "$(json_escape "$backup_target")" "$(json_escape "$backup_dir")" \
      "$(json_escape "$target")" "$(json_escape "$backup_target")" "$(json_escape "$candidate")" "$(json_escape "$target")"
    return 0
  fi

  local restore="not_needed"
  if [[ "$moved_target" == "true" && ! -e "$target" && -e "$backup_target" ]]; then
    if mv "$backup_target" "$target"; then
      restore="restored_target"
    else
      restore="restore_failed"
    fi
  fi
  printf '{"status":"error","operation":"replace-with-candidate","message":"failed to move candidate to target","target":"%s","candidate":"%s","backup_path":"%s","restore":"%s","next_valid_actions":["inspect-paths","fix-candidate","retry-after-confirmation"]}\n' \
    "$(json_escape "$target")" "$(json_escape "$candidate")" "$(json_escape "$backup_target")" "$(json_escape "$restore")"
  exit 1
}

move_sources() {
  local destination=""
  local sources=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --destination) destination="${2:-}"; shift 2 ;;
      --source) sources+=("${2:-}"); shift 2 ;;
      *) die "Unknown argument: $1" ;;
    esac
  done

  [[ -n "$destination" ]] || die "--destination is required"
  assert_abs "$destination" "--destination"
  [[ "${#sources[@]}" -gt 0 ]] || die "At least one --source is required"
  for src in "${sources[@]}"; do
    assert_abs "$src" "--source"
    [[ -f "$src" ]] || die "Source not found: $src"
  done

  mkdir -p "$destination"
  local moved_from=()
  local moved_to=()

  for src in "${sources[@]}"; do
    local dest="$destination/${src##*/}"
    if [[ -e "$dest" ]]; then
      for (( idx=${#moved_from[@]}-1; idx>=0; idx-- )); do
        [[ -e "${moved_to[$idx]}" && ! -e "${moved_from[$idx]}" ]] && mv "${moved_to[$idx]}" "${moved_from[$idx]}" || true
      done
      die "Destination already exists: $dest"
    fi
    if mv "$src" "$dest"; then
      moved_from+=("$src")
      moved_to+=("$dest")
    else
      for (( idx=${#moved_from[@]}-1; idx>=0; idx-- )); do
        [[ -e "${moved_to[$idx]}" && ! -e "${moved_from[$idx]}" ]] && mv "${moved_to[$idx]}" "${moved_from[$idx]}" || true
      done
      die "Failed to move source: $src"
    fi
  done

  local moved_json=""
  for (( idx=0; idx<${#moved_from[@]}; idx++ )); do
    [[ -n "$moved_json" ]] && moved_json+=","
    moved_json+='{"from":"'"$(json_escape "${moved_from[$idx]}")"'","to":"'"$(json_escape "${moved_to[$idx]}")"'"}'
  done
  printf '{"status":"success","operation":"move-sources","destination_dir":"%s","moved":[%s]}\n' "$(json_escape "$destination")" "$moved_json"
}

check_paths() {
  local paths=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --path) paths+=("${2:-}"); shift 2 ;;
      *) die "Unknown argument: $1" ;;
    esac
  done
  [[ "${#paths[@]}" -gt 0 ]] || die "At least one --path is required"
  local items=""
  for path in "${paths[@]}"; do
    assert_abs "$path" "--path"
    local exists="false"
    local is_file="false"
    local is_dir="false"
    [[ -e "$path" ]] && exists="true"
    [[ -f "$path" ]] && is_file="true"
    [[ -d "$path" ]] && is_dir="true"
    [[ -n "$items" ]] && items+=","
    items+='{"path":"'"$(json_escape "$path")"'","exists":'"$exists"',"is_file":'"$is_file"',"is_dir":'"$is_dir"'}'
  done
  printf '{"status":"success","operation":"check-paths","items":[%s]}\n' "$items"
}

restore_moved() {
  local pairs=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --pair) pairs+=("${2:-}"); shift 2 ;;
      *) die "Unknown argument: $1" ;;
    esac
  done
  [[ "${#pairs[@]}" -gt 0 ]] || die "At least one --pair from=to is required"
  local restored=""
  for pair in "${pairs[@]}"; do
    local from="${pair%%=*}"
    local to="${pair#*=}"
    assert_abs "$from" "--pair from"
    assert_abs "$to" "--pair to"
    [[ -e "$from" ]] || die "Restore source not found: $from"
    [[ ! -e "$to" ]] || die "Restore destination already exists: $to"
    mv "$from" "$to"
    [[ -n "$restored" ]] && restored+=","
    restored+='{"from":"'"$(json_escape "$from")"'","to":"'"$(json_escape "$to")"'"}'
  done
  printf '{"status":"success","operation":"restore-moved","restored":[%s]}\n' "$restored"
}

OPERATION="${1:-}"
[[ -n "$OPERATION" ]] || die "Operation is required"
shift || true

case "$OPERATION" in
  replace-with-candidate) replace_with_candidate "$@" ;;
  move-sources) move_sources "$@" ;;
  check-paths) check_paths "$@" ;;
  restore-moved) restore_moved "$@" ;;
  *) die "Unknown operation: $OPERATION" ;;
esac
