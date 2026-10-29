#!/usr/bin/env bash
# Gera usuário e senha do MLflow: o hash vai para o .env, a senha em texto vai só para um arquivo 600
# fora do repositório, para repassar a quem for acessar. Não imprime a senha.
# Uso: scripts/mlflow_credentials.sh [.env] [arquivo-da-senha]
set -euo pipefail
env_file=${1:-.env}
out=${2:-$HOME/.callseg_mlflow_login}
user=visitante
pass=$(openssl rand -base64 24 | tr -d '/+=' | cut -c1-24)
hash=$(docker run --rm caddy:2.11.7-alpine caddy hash-password --plaintext "$pass")
sed -i '/^MLFLOW_BASIC_/d' "$env_file"
printf "MLFLOW_BASIC_USER=%s\nMLFLOW_BASIC_HASH='%s'\n" "$user" "$hash" >> "$env_file"
umask 177
printf "usuario: %s\nsenha: %s\n" "$user" "$pass" > "$out"
echo "hash gravado em $env_file; usuário e senha em $out (modo 600)"
