# Simulação de Alocação Indexada por I-nodes

Trabalho 3 — Sistemas Operacionais (IFCE Campus Maracanaú, Prof. Daniel Ferreira)
**Tema escolhido:** Implementação de alocação indexada por i-nodes

## Visão geral

Este projeto simula, em Python puro (sem dependências externas para o
simulador em si), um sistema de arquivos que usa **alocação indexada por
i-nodes** no estilo clássico do Unix (V7 / ext2): cada i-node guarda
ponteiros **diretos** e três níveis de **indireção** (simples, dupla e
tripla), permitindo endereçar arquivos pequenos com poucos acessos a
disco e arquivos grandes através de blocos extras de ponteiros.

```
i-node
 ├── ponteiros diretos[D]        -> bloco de dados            (1 acesso)
 ├── indireto simples            -> bloco de ponteiros -> dado (2 acessos)
 ├── indireto duplo              -> ponteiros -> ponteiros -> dado (3 acessos)
 └── indireto triplo             -> 3 níveis de ponteiros -> dado (4 acessos)
```

## Estrutura do projeto

```
inode_fs/
├── src/
│   ├── virtual_disk.py    # disco virtual: blocos, bitmap de livres, contagem de I/O
│   ├── inode.py           # estrutura do i-node (ponteiros diretos/indiretos)
│   ├── filesystem.py      # lógica de alocação indexada, leitura, escrita, remoção
│   ├── main.py             # demonstração executável (entradas e saídas de exemplo)
│   └── benchmark.py        # varredura de tamanhos + gráfico de métricas
├── tests/
│   └── test_filesystem.py  # testes automatizados (unittest)
└── README.md
```

## Como executar

Requer apenas Python 3 (testado em 3.10+). Nenhuma dependência externa é
necessária para `main.py`; `benchmark.py` usa `matplotlib` apenas para
gerar o gráfico (opcional).

```bash
cd src
python3 main.py
```

Parâmetros opcionais (para experimentar outras configurações de disco):

```bash
python3 main.py --block-size 16 --direct 4 --total-blocks 300
```

### Testes automatizados

```bash
python3 -m unittest tests.test_filesystem -v
```

### Benchmark / gráfico de métricas

```bash
pip install matplotlib --break-system-packages   # se necessário
cd src
python3 benchmark.py
# gera benchmark_resultados.csv e benchmark_grafico.png
```

## O que a demonstração (`main.py`) mostra

1. **Criação de 4 arquivos** de tamanhos crescentes, cada um atravessando
   um nível diferente de indireção (direto → simples → duplo → triplo).
2. **Estrutura interna dos i-nodes** de cada arquivo criado.
3. **Verificação de corretude**: os dados lidos são comparados aos dados
   originalmente escritos.
4. **Métricas de desempenho por arquivo**: blocos de dados x blocos de
   ponteiros (overhead de metadados), nível máximo de indireção atingido,
   número de acessos a disco e fragmentação interna.
5. **Custo de acesso aleatório**: quantos acessos a disco são necessários
   para alcançar bytes em diferentes posições do arquivo.
6. **Cache de blocos de ponteiros**: comparação do número de leituras
   físicas em uma leitura sequencial **com** e **sem** um cache simples
   de blocos de indireção (simula o efeito de um buffer cache real).
7. **Remoção de arquivo**: liberação de todos os blocos (dados + ponteiros)
   sem vazamentos.
8. **Resumo final** de uso do disco virtual.

## Principais métricas de desempenho avaliadas

| Métrica | Descrição |
|---|---|
| Acessos a disco por nível | direto=1, indireto simples=2, duplo=3, triplo=4 |
| Overhead de metadados | % dos blocos do arquivo que são blocos de ponteiros, não dados |
| Fragmentação interna | bytes desperdiçados no último bloco parcialmente ocupado |
| Efeito de cache | redução nas leituras físicas ao cachear blocos de ponteiros recém-lidos |
| Tamanho máximo de arquivo | D + P + P² + P³ blocos, onde P = block_size / 4 bytes |

Com os parâmetros padrão da demo (`block_size=16`, `D=4`, logo `P=4`):
tamanho máximo de arquivo = 4 + 4 + 16 + 64 = **88 blocos = 1408 bytes**.
Os parâmetros são pequenos de propósito, apenas para que a simulação
percorra **todos os níveis de indireção** (incluindo o triplo) em
exemplos pequenos e fáceis de visualizar/depurar. Com parâmetros
realistas (ex.: blocos de 4 KB, ponteiros de 4 bytes → P=1024), a mesma
implementação suportaria arquivos de centenas de gigabytes, exatamente
como em um sistema de arquivos Unix real.

## Equipe

> Preencher com os nomes dos integrantes do grupo antes do envio.

- Nome 1
- Nome 2
- Nome 3
- Nome 4
