# ADR 0015: Kubernetes não adotado

**Estado:** aceito.

## Contexto
A pilha tem quatro serviços de longa duração (API, banco, Metabase, MLflow), mais Airflow quando agendado, e etapas de lote. Kubernetes é a ferramenta padrão para orquestrar contêineres, então a pergunta é se ele serve aqui.

## Decisão
Usar **Docker Compose em um único host**.

## Motivos
- **Uma máquina.** O principal ganho do Kubernetes, distribuir carga e recuperar nó perdido entre várias máquinas, não existe com um host.
- **Peso operacional.** O plano de controle consome memória que a pilha toda precisa, e exige conhecimento de rede, armazenamento e segredos próprios do cluster para depurar um erro simples.
- **Escala previsível.** Uma chamada leva poucos milissegundos (mediana de cerca de 4 ms em máquina ociosa); uma réplica atende dezenas de requisições por segundo, e a demanda é a de uma demonstração.
- **Equivalência.** Os contêineres já são sem estado (o modelo é somente leitura, o estado está no banco), então a migração futura é traduzir o compose para manifestos, sem reescrever código.

## Quando rever
Mais de um servidor, necessidade de implantação sem indisponibilidade com várias réplicas da API, ou outras equipes publicando serviços na mesma infraestrutura. O caminho natural é um cluster leve (k3s) com a API em `Deployment`, o banco gerenciado fora do cluster e o Airflow com o executor de Kubernetes.
