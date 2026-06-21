"""
main.py
-------
Demonstracao executavel da simulacao de ALOCACAO INDEXADA POR I-NODES.

Uso:
    python3 main.py                     # roda com os parametros padrao da demo
    python3 main.py --block-size 16 --direct 4 --total-blocks 300

O script:
    1. Cria um disco virtual e um sistema de arquivos baseado em i-nodes.
    2. Cria 4 arquivos de tamanhos crescentes, cada um exercitando um nivel
       diferente de indirecao (direto, indireto simples, duplo e triplo).
    3. Mostra a estrutura interna do i-node de cada arquivo.
    4. Verifica a corretude da leitura (dados lidos == dados escritos).
    5. Mede o custo de acesso (numero de I/Os) para alcancar bytes em
       diferentes posicoes do arquivo.
    6. Compara o numero de acessos fisicos a disco em uma leitura
       sequencial COM e SEM cache de blocos de ponteiros.
    7. Remove um arquivo e mostra a liberacao de blocos (sem vazamentos).
    8. Imprime um resumo final de uso do disco.
"""

from __future__ import annotations
import argparse
import os
import sys

from virtual_disk import VirtualDisk, DiskFullError
from filesystem import FileSystem, FileTooLargeError


def hr(ch: str = "-", width: int = 78) -> None:
    print(ch * width)


def titulo(texto: str) -> None:
    hr("=")
    print(texto)
    hr("=")


def parse_args():
    p = argparse.ArgumentParser(description="Simulacao de alocacao indexada por i-nodes")
    p.add_argument("--block-size", type=int, default=16,
                    help="Tamanho do bloco em bytes (default: 16)")
    p.add_argument("--direct", type=int, default=4,
                    help="Numero de ponteiros diretos no i-node (default: 4)")
    p.add_argument("--total-blocks", type=int, default=300,
                    help="Total de blocos do disco virtual (default: 300)")
    return p.parse_args()


def main():
    args = parse_args()

    titulo("SIMULACAO: ALOCACAO INDEXADA POR I-NODES")
    print(f"Parametros do disco virtual:")
    print(f"  - Tamanho do bloco ......... {args.block_size} bytes")
    print(f"  - Ponteiros diretos (D) .... {args.direct}")
    print(f"  - Total de blocos do disco . {args.total_blocks}")

    disk = VirtualDisk(total_blocks=args.total_blocks, block_size=args.block_size)
    fs = FileSystem(disk, num_direct=args.direct)

    print(f"  - Ponteiros por bloco (P) .. {fs.P}  (= block_size / 4 bytes)")
    print(f"  - Capacidade so' direto .... {fs.D} blocos = {fs.D * args.block_size} bytes")
    print(f"  - Capacidade indireto simples = {fs.single_capacity} blocos adicionais")
    print(f"  - Capacidade indireto duplo   = {fs.double_capacity} blocos adicionais")
    print(f"  - Capacidade indireto triplo  = {fs.triple_capacity} blocos adicionais")
    print(f"  - TAMANHO MAXIMO DE ARQUIVO   = {fs.max_blocks_per_file} blocos "
          f"= {fs.max_file_size_bytes} bytes")
    print()

    # ------------------------------------------------------------------
    # 1) Criacao de arquivos de tamanhos crescentes
    # ------------------------------------------------------------------
    titulo("1) CRIACAO DE ARQUIVOS (entrada)")

    # Tamanhos escolhidos propositalmente para atravessar cada nivel de
    # indirecao dado D=4 e P=4 (block_size=16): direto<=64B, simples<=128B,
    # duplo<=384B, triplo<=1408B (com os parametros default).
    direct_cap = fs.D * args.block_size
    single_cap = (fs.D + fs.single_capacity) * args.block_size
    double_cap = (fs.D + fs.single_capacity + fs.double_capacity) * args.block_size
    triple_cap = fs.max_file_size_bytes

    tamanhos = {
        "pequeno.txt": max(8, direct_cap - args.block_size // 2),
        "medio.txt": min(single_cap - 4, single_cap - args.block_size // 4) if single_cap > direct_cap else direct_cap + 4,
        "grande.txt": double_cap - args.block_size if double_cap > single_cap else single_cap + 4,
        "enorme.txt": min(triple_cap, double_cap + args.block_size * 5) if triple_cap > double_cap else double_cap + 4,
    }

    originais = {}
    for nome, tamanho in tamanhos.items():
        tamanho = max(1, min(tamanho, fs.max_file_size_bytes))
        dados = os.urandom(tamanho)
        try:
            fs.create_file(nome, dados)
            originais[nome] = dados
            print(f"  [OK] '{nome}' criado com {tamanho} bytes")
        except FileTooLargeError as e:
            print(f"  [ERRO] '{nome}': {e}")

    print()

    # ------------------------------------------------------------------
    # 2) Estrutura interna dos i-nodes
    # ------------------------------------------------------------------
    titulo("2) ESTRUTURA INTERNA DOS I-NODES")
    for nome in originais:
        inode_num = fs.directory[nome]
        inode = fs.inodes[inode_num]
        print(f"  {nome}: {inode}")
    print()

    # ------------------------------------------------------------------
    # 3) Verificacao de corretude da leitura (saida)
    # ------------------------------------------------------------------
    titulo("3) LEITURA E VERIFICACAO DE CORRETUDE (saida)")
    for nome, dados_originais in originais.items():
        resultado = fs.read_file(nome)
        correto = resultado.data == dados_originais
        status = "OK (dados identicos)" if correto else "FALHOU (dados diferentes!)"
        print(f"  {nome}: {status} | "
              f"{resultado.logical_block_accesses} blocos logicos | "
              f"{resultado.physical_disk_reads} leituras fisicas")
    print()

    # ------------------------------------------------------------------
    # 4) Metricas de desempenho por arquivo
    # ------------------------------------------------------------------
    titulo("4) METRICAS DE DESEMPENHO POR ARQUIVO")
    cab = f"{'arquivo':<14}{'tam(B)':>8}{'blocos':>8}{'ptr-blk':>9}{'overhead%':>11}{'nivel':>9}{'acessos':>9}{'fragm(B)':>10}"
    print(cab)
    hr()
    for nome in originais:
        st = fs.file_stats(nome)
        print(f"{st['nome']:<14}{st['tamanho_bytes']:>8}{st['blocos_totais']:>8}"
              f"{st['blocos_de_ponteiros']:>9}{st['overhead_metadados_pct']:>10}%"
              f"{st['nivel_max_indirecao']:>10}{st['acessos_max_a_disco']:>9}"
              f"{st['fragmentacao_interna_bytes']:>10}")
    print()
    print("  'acessos' = numero de leituras a disco necessarias para alcancar")
    print("  o ULTIMO bloco do arquivo (1=direto, 2=indireto simples, 3=duplo, 4=triplo).")
    print()

    # ------------------------------------------------------------------
    # 5) Custo de acesso ALEATORIO em diferentes posicoes do arquivo
    # ------------------------------------------------------------------
    titulo("5) CUSTO DE ACESSO ALEATORIO (acesso direto a um byte qualquer)")
    maior_arquivo = max(originais, key=lambda n: len(originais[n]))
    tam = len(originais[maior_arquivo])
    print(f"  Arquivo de teste: '{maior_arquivo}' ({tam} bytes)")
    posicoes_relativas = [0.0, 0.25, 0.5, 0.75, 0.99]
    for frac in posicoes_relativas:
        offset = min(tam - 1, int(frac * tam))
        logical_block = offset // args.block_size
        nivel, _ = fs._locate(logical_block)
        custo = fs.access_cost(nivel)
        print(f"  byte {offset:>6} (bloco logico {logical_block:>3}) -> "
              f"nivel '{nivel}' -> {custo} acesso(s) a disco")
    print()
    print("  Observacao: quanto mais 'para dentro' do arquivo, maior o numero de")
    print("  niveis de indirecao percorridos e maior o custo de acesso aleatorio.")
    print()

    # ------------------------------------------------------------------
    # 6) Efeito do cache de blocos de ponteiros (leitura sequencial)
    # ------------------------------------------------------------------
    titulo("6) LEITURA SEQUENCIAL: COM x SEM CACHE DE BLOCOS DE PONTEIROS")
    for nome in originais:
        sem = fs.read_file(nome, use_cache=False)
        com = fs.read_file(nome, use_cache=True)
        if sem.physical_disk_reads > 0:
            reducao = 100 * (1 - com.physical_disk_reads / sem.physical_disk_reads)
        else:
            reducao = 0.0
        print(f"  {nome:<14} sem cache: {sem.physical_disk_reads:>4} I/Os  |  "
              f"com cache: {com.physical_disk_reads:>4} I/Os  |  reducao: {reducao:5.1f}%")
    print()
    print("  O cache evita reler o mesmo bloco de ponteiros (indireto/duplo/triplo)")
    print("  quando blocos de dados vizinhos pertencem ao mesmo bloco de indirecao --")
    print("  um ganho tipico de localidade explorado por caches de buffer reais.")
    print()

    # ------------------------------------------------------------------
    # 7) Remocao de arquivo e liberacao de blocos
    # ------------------------------------------------------------------
    titulo("7) REMOCAO DE ARQUIVO E LIBERACAO DE BLOCOS")
    alvo = maior_arquivo
    antes_usados = disk.used_blocks_count()
    antes_livres = disk.free_blocks_count()
    print(f"  Antes de remover '{alvo}': {antes_usados} blocos usados, {antes_livres} livres")
    fs.delete_file(alvo)
    depois_usados = disk.used_blocks_count()
    depois_livres = disk.free_blocks_count()
    print(f"  Depois de remover '{alvo}': {depois_usados} blocos usados, {depois_livres} livres")
    print(f"  Blocos liberados: {antes_usados - depois_usados}")
    del originais[alvo]
    print()

    # ------------------------------------------------------------------
    # 8) Resumo final de uso do disco
    # ------------------------------------------------------------------
    titulo("8) RESUMO FINAL DE USO DO DISCO")
    print(f"  Blocos totais .......... {disk.total_blocks}")
    print(f"  Blocos em uso .......... {disk.used_blocks_count()}")
    print(f"  Blocos livres .......... {disk.free_blocks_count()}")
    print(f"  Alocacoes realizadas ... {disk.allocations}")
    print(f"  Liberacoes realizadas .. {disk.frees}")
    print(f"  Leituras fisicas (total) {disk.physical_reads}")
    print(f"  Escritas fisicas (total) {disk.physical_writes}")
    hr("=")


if __name__ == "__main__":
    try:
        main()
    except DiskFullError as e:
        print(f"Erro: {e}", file=sys.stderr)
        sys.exit(1)
