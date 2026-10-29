# CI e CD: o que cada workflow faz

Os três workflows ficam em `.github/workflows/`.

## `ci.yml`: roda em todo push na `main` e em todo pull request

**Job `test`** (rápido, sem Docker):
1. instala as dependências travadas (`uv sync --frozen`);
2. `ruff check` (estilo e erros comuns);
3. `pip-audit` sobre as dependências de execução (vulnerabilidades conhecidas);
4. confere que nenhum dado, modelo ou `.env` está no git;
5. `pytest`: os testes do modelo, dos dados em camadas, do banco (SQLite), da API, do portão de promoção, da deriva e da CLI. **Sim, os testes estão nas Actions.** Eles usam um corpus sintético, por isso não precisam do dataset.

**Job `image`** (depois do `test`):
1. treina o modelo sintético e sobe a pilha real (`docker compose up --build --wait`);
2. chama a API de verdade e confere que a chamada de pet virou `medicare`;
3. confere que o papel de leitura do BI **não** consegue apagar predições (permissão negada) e que a predição foi gravada;
4. confere que as quatro camadas do banco foram criadas pela migração;
5. varre a imagem com Trivy (vulnerabilidades críticas com correção disponível reprovam).

## `release.yml`: roda quando se cria uma tag `v*`

É aqui que a **release** entra. Uma tag (por exemplo `v0.2.0`) dispara a construção da imagem de `docker/api.Dockerfile` e a publicação no GHCR (`ghcr.io/<dono>/call-segmenter:0.2.0`, mais uma tag pelo hash do commit). A imagem publicada é o que a produção usa. Fluxo: CI verde na `main`, `git tag v0.2.0`, `git push --tags`.

## `deploy.yml`: execução manual

Roda no servidor, num runner próprio. Recebe a versão da imagem, baixa a imagem do GHCR, sobe só o que mudou com `deploy/compose.prod.yml` e confere o `/health`. É manual de propósito: quem decide trocar a versão em produção é uma pessoa.

## Ordem para colocar uma versão no ar

1. Merge na `main` com o CI verde.
2. Tag `vX.Y.Z` (o `release` publica a imagem).
3. Rodar o `deploy` com a versão.
4. Se mudou o modelo: `make train promote` e copiar o `.joblib` para o servidor (ver `deploy/README.md`).
