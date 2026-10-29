#!/bin/sh
# Importa o que tools/export_aggregates.sh gerou para o banco do ambiente atual, substituindo as linhas
# anteriores dessas tabelas (e as predições do conjunto de dados). Roda no diretório do compose.
#   sh tools/import_aggregates.sh [DIR]
set -eu
dir=${1:-reports/export}
run_sql() { docker compose exec -T db sh -c "psql -U \$POSTGRES_USER -d \$POSTGRES_DB -v ON_ERROR_STOP=1 -c \"$1\""; }
load() { docker compose exec -T db sh -c "psql -U \$POSTGRES_USER -d \$POSTGRES_DB -v ON_ERROR_STOP=1 -c \"\\copy $1 from stdin with csv header\"" < "$dir/$2.csv"; }
run_sql "truncate gold.holdout_confusion, gold.model_versions, gold.sector_profile, gold.size_histogram, gold.subgroup_analysis, ops.model_benchmark"
run_sql "delete from gold.dataset_versions"
run_sql "delete from ops.predictions where source = 'dataset'"
load gold.dataset_versions gold.dataset_versions
load gold.sector_profile gold.sector_profile
load gold.size_histogram gold.size_histogram
load gold.subgroup_analysis gold.subgroup_analysis
load gold.model_versions gold.model_versions
load gold.holdout_confusion gold.holdout_confusion
load ops.model_benchmark ops.model_benchmark
load "ops.predictions(request_id, ts, source, model_version, sector, sector_probability, low_confidence, subgroup_id, subgroup_name, margin, ambiguous, n_words, latency_ms, text_sha256)" ops.predictions
echo "agregados importados"
