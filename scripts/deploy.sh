#!/usr/bin/env bash
# Deploy an already built image using a temporary CI env file or the server .env.
set -euo pipefail
umask 077

app_dir=/opt/legal-assistant
container=legal-assistant
backup=legal-assistant-previous
revision="${1:?Usage: bash deploy.sh COMMIT_SHA [IMAGE_ARCHIVE] [RUNTIME_ENV_FILE]}"
archive="${2:-}"
runtime_env="${3:-}"
env_file="${runtime_env:-$app_dir/.env}"
if [[ -n "$runtime_env" && "$runtime_env" != "$app_dir/incoming/"*"/runtime.env" ]]; then
  echo 'The temporary environment file must be incoming/RUN/runtime.env.' >&2
  exit 1
fi
cleanup_runtime_env() {
  if [[ -n "$runtime_env" ]]; then
    rm -f -- "$runtime_env"
  fi
}
trap cleanup_runtime_env EXIT
[[ "$revision" =~ ^[a-f0-9]{40}$ ]] || { echo 'Expected a full commit SHA.' >&2; exit 1; }
image="legal-assistant:$revision"

command -v flock >/dev/null
test -d "$app_dir"
exec 9>"$app_dir/.deploy.lock"
flock -w 300 9

if [[ ! -r "$env_file" ]]; then
  echo 'Provide model configuration through GitHub production Secrets or the server .env file.' >&2
  exit 1
fi
if ! grep -Eq '^LLM_API_KEY=.+$' "$env_file"; then
  echo 'Set LLM_API_KEY in the deployment environment file.' >&2
  exit 1
fi
docker info >/dev/null

if [[ -n "$archive" ]]; then
  gzip -dc -- "$archive" | docker load
fi
docker image inspect "$image" >/dev/null

# A backup left by an interrupted deployment requires recovery first.
if docker container inspect "$backup" >/dev/null 2>&1; then
  echo "Container $backup already exists. See docs/DEPLOYMENT.md for recovery." >&2
  exit 1
fi

if [[ "${BASH_SOURCE[0]}" != "$app_dir/deploy.sh" ]]; then
  install -m 700 "${BASH_SOURCE[0]}" "$app_dir/deploy.sh"
fi

had_previous=false
replacement_started=false
deployed=false
previous_image=''

finish() {
  local status=$?
  trap - EXIT
  if [[ "$deployed" != true ]]; then
    if [[ "$replacement_started" == true ]]; then
      docker rm -f "$container" >/dev/null 2>&1 || true
    fi
    if [[ "$had_previous" == true ]]; then
      echo 'Deployment failed; restoring the previous container.' >&2
      if docker rename "$backup" "$container" && docker start "$container" >/dev/null; then
        echo 'Previous container restarted; check its health before continuing.' >&2
      else
        echo "Automatic recovery failed. Recover $backup manually." >&2
      fi
    fi
  fi
  cleanup_runtime_env
  exit "$status"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if docker container inspect "$container" >/dev/null 2>&1; then
  previous_image="$(docker inspect --format '{{.Config.Image}}' "$container")"
  docker rename "$container" "$backup"
  had_previous=true
  docker stop --time 30 "$backup" >/dev/null
fi

replacement_started=true
docker run -d \
  --name "$container" \
  --pull never \
  --restart unless-stopped \
  --env-file "$env_file" \
  --env HOST=0.0.0.0 \
  --env PORT=8000 \
  --publish 8000:8000 \
  --log-driver json-file \
  --log-opt max-size=10m \
  --log-opt max-file=3 \
  "$image" >/dev/null

healthy=false
for attempt in {1..60}; do
  health="$(docker inspect --format '{{.State.Health.Status}}' "$container")"
  if [[ "$health" == healthy ]]; then
    healthy=true
    break
  fi
  if [[ "$health" == unhealthy ]]; then
    break
  fi
  sleep 2
done
if [[ "$healthy" != true ]]; then
  echo 'The new container did not become healthy.' >&2
  docker logs --tail 100 "$container" >&2 || true
  exit 1
fi

if [[ -n "$previous_image" ]]; then
  printf '%s\n' "$previous_image" > "$app_dir/.previous-image"
fi
printf '%s\n' "$image" > "$app_dir/.deployed-image"
deployed=true
if [[ "$had_previous" == true ]]; then
  docker rm "$backup" >/dev/null
fi
echo "Deployed $image. Application environment injected into the container."
