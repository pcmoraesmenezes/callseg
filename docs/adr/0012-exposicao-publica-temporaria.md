# ADR 0012: exposição pública temporária em duas camadas

**Estado:** aceito para a demonstração; o serviço é derrubado depois.

## Contexto
A demonstração precisa ser aberta a qualquer visitante, sem conta e sem acesso à máquina.

## Decisão
Duas camadas, por um túnel reverso (o IP do servidor não é aberto):
- **Aberta, sem login:** a API com a página de demonstração e os painéis públicos do Metabase. Devolvem classificação do texto que o próprio visitante envia e agregados; nada de dado de terceiros.
- **Com senha:** o MLflow, por proxy com autenticação básica. Ele não tem login e quem entra apaga execuções e modelos.
- **Interna:** banco, deriva e administração do servidor, sem porta exposta.
Sem limite de taxa, por decisão de projeto.

## Alternativas consideradas
- **Provedor de identidade na frente de tudo**: exigiria que quem avalia tivesse conta no provedor.
- **Tudo fechado, com capturas de tela**: perde a possibilidade de usar a API de verdade.

## Consequências
- A conta de administração do Metabase fica na mesma URL dos painéis públicos; a defesa é senha longa e cadastro desligado.
- A senha básica não bloqueia tentativas, por isso é longa e aleatória.
- Os contêineres rodam sem privilégios (`no-new-privileges`, `cap_drop ALL`, sistema de arquivos somente leitura onde possível).

## Como derrubar
`docker compose --profile bi --profile mlops --profile orchestration down -v` e a remoção das rotas do túnel.
