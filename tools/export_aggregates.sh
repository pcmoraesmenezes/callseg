#!/bin/sh
# Exporta do banco local só agregados e predições (nunca texto): tabelas de ouro do modelo vigente,
# comparação de modelos e predições do conjunto de dados. Saída em DIR (padrão reports/export).
#   sh tools/export_aggregates.sh [DIR]
set -eu
dir=${1:-reports/export}
mkdir -p "$dir"
psql_local() { docker compose exec -T db sh -c "psql -U \$POSTGRES_USER -d \$POSTGRES_DB -v ON_ERROR_STOP=1 -c \"$1\""; }
champion=$(docker compose exec -T db sh -c "psql -U \$POSTGRES_USER -d \$POSTGRES_DB -tAc \"select model_version from gold.model_versions where status = 'champion'\"" | tr -d '\r')
[ -n "$champion" ] || { echo "nenhum modelo vigente em gold.model_versions" >&2; exit 1; }
for table in gold.dataset_versions gold.sector_profile gold.size_histogram gold.subgroup_analysis ops.model_benchmark; do
  psql_local "\\copy $table to stdout with csv header" > "$dir/$table.csv"
done
for table in gold.model_versions gold.holdout_confusion; do
  psql_local "\\copy (select * from $table where model_version = '$champion') to stdout with csv header" > "$dir/$table.csv"
done
psql_local "\\copy (select request_id, ts, source, model_version, sector, sector_probability, low_confidence, subgroup_id, subgroup_name, margin, ambiguous, n_words, latency_ms, text_sha256 from ops.predictions where source = 'dataset') to stdout with csv header" > "$dir/ops.predictions.csv"
echo "exportado em $dir (modelo vigente $champion)"
