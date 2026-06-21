"""
benchmark.py
------------
Varre uma faixa de tamanhos de arquivo e mede, para cada tamanho:
    - blocos de dados x blocos de ponteiros (overhead de metadados)
    - nivel maximo de indirecao atingido
    - acessos a disco necessarios para alcancar o ultimo bloco
    - leituras fisicas em uma leitura sequencial COM e SEM cache

Gera:
    - benchmark_resultados.csv : tabela completa
    - benchmark_grafico.png    : grafico comparativo (usado no resumo/relatorio)

Requer matplotlib apenas para o grafico (nao e dependencia do simulador em si).
"""
from __future__ import annotations
import csv
import os
import sys

from virtual_disk import VirtualDisk
from filesystem import FileSystem

BLOCK_SIZE = 16
NUM_DIRECT = 4
TOTAL_BLOCKS = 2000  # disco maior para comportar a varredura completa


def run_benchmark():
    disk = VirtualDisk(total_blocks=TOTAL_BLOCKS, block_size=BLOCK_SIZE)
    fs = FileSystem(disk, num_direct=NUM_DIRECT)

    max_size = fs.max_file_size_bytes
    # 20 tamanhos distribuidos entre 1 byte e o tamanho maximo suportado
    passos = 20
    tamanhos = sorted(set(
        max(1, int(max_size * i / passos)) for i in range(1, passos + 1)
    ))

    linhas = []
    for tamanho in tamanhos:
        nome = f"arq_{tamanho}.bin"
        dados = os.urandom(tamanho)
        fs.create_file(nome, dados)

        stats = fs.file_stats(nome)
        sem_cache = fs.read_file(nome, use_cache=False)
        com_cache = fs.read_file(nome, use_cache=True)
        reducao = (100 * (1 - com_cache.physical_disk_reads / sem_cache.physical_disk_reads)
                   if sem_cache.physical_disk_reads else 0.0)

        linhas.append({
            "tamanho_bytes": tamanho,
            "blocos_dados": stats["blocos_de_dados"],
            "blocos_ponteiros": stats["blocos_de_ponteiros"],
            "overhead_pct": stats["overhead_metadados_pct"],
            "nivel_max": stats["nivel_max_indirecao"],
            "acessos_max": stats["acessos_max_a_disco"],
            "io_sem_cache": sem_cache.physical_disk_reads,
            "io_com_cache": com_cache.physical_disk_reads,
            "reducao_cache_pct": round(reducao, 1),
        })

        fs.delete_file(nome)  # libera espaco para o proximo tamanho da varredura

    return linhas


def save_csv(linhas, path):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        writer.writeheader()
        writer.writerows(linhas)
    print(f"CSV salvo em: {path}")


def save_chart(linhas, path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib nao instalado -- pulando geracao do grafico.", file=sys.stderr)
        return

    tamanhos = [l["tamanho_bytes"] for l in linhas]
    overhead = [l["overhead_pct"] for l in linhas]
    io_sem = [l["io_sem_cache"] for l in linhas]
    io_com = [l["io_com_cache"] for l in linhas]

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))

    axes[0].plot(tamanhos, overhead, marker="o", color="#2E75B6")
    axes[0].set_title("Overhead de metadados vs. tamanho do arquivo")
    axes[0].set_xlabel("Tamanho do arquivo (bytes)")
    axes[0].set_ylabel("Blocos de ponteiros / total (%)")
    axes[0].grid(alpha=0.3)

    axes[1].plot(tamanhos, io_sem, marker="o", label="Sem cache", color="#C0392B")
    axes[1].plot(tamanhos, io_com, marker="s", label="Com cache", color="#27AE60")
    axes[1].set_title("Leituras fisicas (sequencial): com x sem cache")
    axes[1].set_xlabel("Tamanho do arquivo (bytes)")
    axes[1].set_ylabel("Leituras fisicas a disco")
    axes[1].legend()
    axes[1].grid(alpha=0.3)

    fig.suptitle("Alocacao indexada por i-nodes -- metricas de desempenho", fontsize=12)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    print(f"Grafico salvo em: {path}")


if __name__ == "__main__":
    linhas = run_benchmark()
    out_dir = os.path.dirname(os.path.abspath(__file__))
    save_csv(linhas, os.path.join(out_dir, "benchmark_resultados.csv"))
    save_chart(linhas, os.path.join(out_dir, "benchmark_grafico.png"))
