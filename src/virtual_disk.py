"""
virtual_disk.py
----------------
Simula um disco fisico dividido em blocos de tamanho fixo.

Responsabilidades:
    - Alocar e liberar blocos (gerenciamento de espaco livre via bitmap).
    - Ler e escrever blocos.
    - Contar acessos fisicos a disco (metrica de desempenho: numero de I/Os).

Esta classe representa a camada mais baixa da simulacao: ela nao sabe
nada sobre arquivos ou i-nodes, apenas sobre blocos numerados de 0 a N-1.
"""

from __future__ import annotations
from typing import List, Optional


class DiskFullError(Exception):
    """Levantada quando nao ha blocos livres suficientes no disco."""
    pass


class VirtualDisk:
    def __init__(self, total_blocks: int, block_size: int):
        self.total_blocks = total_blocks
        self.block_size = block_size

        # Cada bloco e armazenado como bytearray de tamanho fixo (dados)
        self._blocks: List[Optional[bytearray]] = [None] * total_blocks
        # True = livre, False = ocupado
        self._free_bitmap: List[bool] = [True] * total_blocks

        # ---- metricas de desempenho ----
        self.physical_reads = 0
        self.physical_writes = 0
        self.allocations = 0
        self.frees = 0

    # ------------------------------------------------------------------
    # Gerenciamento de espaco livre (bitmap)
    # ------------------------------------------------------------------
    def free_blocks_count(self) -> int:
        return sum(self._free_bitmap)

    def used_blocks_count(self) -> int:
        return self.total_blocks - self.free_blocks_count()

    def allocate_block(self) -> int:
        """Encontra o primeiro bloco livre (first-fit no bitmap), marca como
        ocupado e devolve seu indice. O(n) -- adequado para fins didaticos;
        uma implementacao real usaria uma estrutura mais eficiente
        (ex.: lista de blocos livres, arvore de bits)."""
        for idx, is_free in enumerate(self._free_bitmap):
            if is_free:
                self._free_bitmap[idx] = False
                self._blocks[idx] = bytearray(self.block_size)
                self.allocations += 1
                return idx
        raise DiskFullError("Disco virtual sem blocos livres.")

    def free_block(self, index: int) -> None:
        if self._free_bitmap[index]:
            return  # ja estava livre
        self._free_bitmap[index] = True
        self._blocks[index] = None
        self.frees += 1

    # ------------------------------------------------------------------
    # Leitura / escrita (cada chamada = 1 acesso fisico ao disco)
    # ------------------------------------------------------------------
    def read_block(self, index: int) -> bytearray:
        self.physical_reads += 1
        block = self._blocks[index]
        if block is None:
            raise ValueError(f"Bloco {index} nao esta alocado.")
        return block

    def write_block(self, index: int, data: bytes) -> None:
        self.physical_writes += 1
        if self._blocks[index] is None:
            raise ValueError(f"Bloco {index} nao esta alocado.")
        buf = bytearray(self.block_size)
        buf[: len(data)] = data
        self._blocks[index] = buf

    # ------------------------------------------------------------------
    # Utilitarios
    # ------------------------------------------------------------------
    def reset_io_counters(self) -> None:
        self.physical_reads = 0
        self.physical_writes = 0

    def __repr__(self) -> str:
        return (f"VirtualDisk(total_blocks={self.total_blocks}, "
                f"block_size={self.block_size}B, "
                f"livres={self.free_blocks_count()}, "
                f"usados={self.used_blocks_count()})")
