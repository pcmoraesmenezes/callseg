# ADR 0013: backend em camadas e frontend em diretório próprio

**Estado:** aceito.

## Contexto
Na primeira versão, um único arquivo de API fazia tudo (rotas, regras, métricas, log, acesso ao banco com SQL escrito à mão) e a página de demonstração morava dentro do pacote da API.

## Decisão
`backend/app/` com uma responsabilidade por módulo:
- `routers/`: recebem a requisição e devolvem a resposta; sem regra de negócio;
- `services/segmentation.py`: chama o modelo, mede, monta resposta e registro de auditoria;
- `call_segmenter.warehouse`: repositórios e modelos ORM (SQLAlchemy 2), com o esquema criado por migrações Alembic e não por SQL solto;
- `schemas.py`, `config.py`, `logging_config.py`, `observability.py`: contratos, configuração, log estruturado e métricas.
O front-end fica em `frontend/` (HTML, CSS e JavaScript estáticos) e é servido pela própria API em `/demo/`.

## Alternativas consideradas
- **Front-end em contêiner próprio (nginx)**: exigiria uma segunda rota pública e coordenar CORS. Para uma página estática de um formulário, não compensa; a separação de diretórios já dá o isolamento que importa (código e testes independentes).
- **Framework de front-end (React)**: dependência e passo de build para uma tela.
- **Domain-driven design completo, com interfaces e injeção em todo lugar**: peso demais para um serviço de duas rotas. Fica o necessário para testar cada camada sozinha (a API recebe o repositório pronto; os testes trocam por um espião).

## Consequências
- Cada camada tem teste próprio; o teste de API não precisa de banco.
- Trocar o acesso a dados (por exemplo, para outro banco) mexe só no pacote `warehouse`.
