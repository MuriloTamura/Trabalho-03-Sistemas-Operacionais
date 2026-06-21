"""
filesystem.py
--------------
Sistema de arquivos didatico que implementa ALOCACAO INDEXADA POR I-NODES,
no estilo classico do Unix (V7 / ext2): cada i-node possui ponteiros
diretos e tres niveis de indirecao (simples, dupla e tripla).

    logico (numero do bloco dentro do arquivo)
        |
        v
    +---------+      direto        -> dado                 (1 acesso a disco)
    | i-node  | -- indireto simples -> bloco ponteiros -> dado (2 acessos)
    |         | -- indireto duplo   -> ponteiros->ponteiros->dado (3 acessos)
    +---------+ -- indireto triplo  -> 3 niveis de ponteiros->dado (4 acessos)

Cada ponteiro ocupa POINTER_SIZE bytes e e armazenado em binario dentro de
um bloco do disco (struct 'i', sentinela -1 = posicao vazia), assim como
ocorreria em um sistema de arquivos real.
"""

from __future__ import annotations
import struct
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from virtual_disk import VirtualDisk, DiskFullError
from inode import Inode

POINTER_SIZE = 4          # bytes por ponteiro (inteiro de 32 bits)
NULL_PTR = -1             # sentinela "posicao vazia" dentro de um bloco de ponteiros


class FileNotFoundInFS(Exception):
    pass


class FileAlreadyExists(Exception):
    pass


class FileTooLargeError(Exception):
    pass


@dataclass
class AccessResult:
    """Resultado de uma leitura: dados lidos + metricas de acesso."""
    data: bytes
    physical_disk_reads: int           # leituras que realmente bateram no disco
    logical_block_accesses: int        # numero de blocos logicos lidos


class FileSystem:
    def __init__(self, disk: VirtualDisk, num_direct: int = 4):
        self.disk = disk
        self.D = num_direct
        # Quantos ponteiros cabem em um bloco de indireção
        self.P = disk.block_size // POINTER_SIZE
        if self.P < 1:
            raise ValueError("block_size precisa ser >= POINTER_SIZE")

        self.inodes: Dict[int, Inode] = {}
        self.directory: Dict[str, int] = {}
        self._next_inode_num = 0

        # Capacidades (em blocos) de cada nivel -- usadas para navegar
        self.single_capacity = self.P
        self.double_capacity = self.P * self.P
        self.triple_capacity = self.P * self.P * self.P
        self.max_blocks_per_file = (
            self.D + self.single_capacity + self.double_capacity + self.triple_capacity
        )
        self.max_file_size_bytes = self.max_blocks_per_file * self.disk.block_size

    # ------------------------------------------------------------------
    # (De)serializacao de blocos de ponteiros
    # ------------------------------------------------------------------
    def _new_pointer_block(self) -> int:
        """Aloca um novo bloco e o inicializa todo com NULL_PTR."""
        idx = self.disk.allocate_block()
        empty = struct.pack(f"<{self.P}i", *([NULL_PTR] * self.P))
        self.disk.write_block(idx, empty)
        return idx

    def _read_pointers(self, block_idx: int) -> List[int]:
        raw = self.disk.read_block(block_idx)
        return list(struct.unpack(f"<{self.P}i", bytes(raw[: self.P * POINTER_SIZE])))

    def _write_pointers(self, block_idx: int, pointers: List[int]) -> None:
        self.disk.write_block(block_idx, struct.pack(f"<{self.P}i", *pointers))

    # ------------------------------------------------------------------
    # Traducao logico -> caminho de indirecao
    # ------------------------------------------------------------------
    def _locate(self, logical_index: int) -> Tuple[str, Tuple[int, ...]]:
        """Devolve (nivel, indices) descrevendo onde o bloco logico mora.

        nivel in {"direct", "single", "double", "triple"}
        indices: posicoes a percorrer dentro de cada nivel de ponteiros.
        """
        if logical_index < self.D:
            return "direct", (logical_index,)

        rem = logical_index - self.D
        if rem < self.single_capacity:
            return "single", (rem,)

        rem -= self.single_capacity
        if rem < self.double_capacity:
            return "double", (rem // self.P, rem % self.P)

        rem -= self.double_capacity
        if rem < self.triple_capacity:
            pp = self.P * self.P
            i1 = rem // pp
            r = rem % pp
            i2 = r // self.P
            i3 = r % self.P
            return "triple", (i1, i2, i3)

        raise FileTooLargeError(
            f"Bloco logico {logical_index} excede o tamanho maximo de arquivo "
            f"({self.max_blocks_per_file} blocos / {self.max_file_size_bytes} bytes)."
        )

    @staticmethod
    def access_cost(level: str) -> int:
        """Numero de acessos a disco necessarios para alcancar o bloco de
        dados a partir do i-node (que assumimos ja estar em memoria,
        premissa classica de SOs: a tabela de i-nodes abertos fica em RAM)."""
        return {"direct": 1, "single": 2, "double": 3, "triple": 4}[level]

    # ------------------------------------------------------------------
    # Alocacao (escrita / crescimento do arquivo)
    # ------------------------------------------------------------------
    def _allocate_logical_block(self, inode: Inode, logical_index: int) -> int:
        """Garante que o bloco logico `logical_index` tenha um bloco de
        dados fisico associado, criando blocos de ponteiros intermediarios
        sob demanda. Devolve o indice fisico do bloco de DADOS."""
        level, idx = self._locate(logical_index)

        if level == "direct":
            (pos,) = idx
            if inode.direct[pos] is None:
                inode.direct[pos] = self.disk.allocate_block()
                inode.blocks_used += 1
            return inode.direct[pos]

        if level == "single":
            (pos,) = idx
            if inode.single_indirect is None:
                inode.single_indirect = self._new_pointer_block()
                inode.blocks_used += 1
            ptrs = self._read_pointers(inode.single_indirect)
            if ptrs[pos] == NULL_PTR:
                ptrs[pos] = self.disk.allocate_block()
                inode.blocks_used += 1
                self._write_pointers(inode.single_indirect, ptrs)
            return ptrs[pos]

        if level == "double":
            i1, i2 = idx
            if inode.double_indirect is None:
                inode.double_indirect = self._new_pointer_block()
                inode.blocks_used += 1
            level1 = self._read_pointers(inode.double_indirect)
            if level1[i1] == NULL_PTR:
                level1[i1] = self._new_pointer_block()
                inode.blocks_used += 1
                self._write_pointers(inode.double_indirect, level1)
            level2 = self._read_pointers(level1[i1])
            if level2[i2] == NULL_PTR:
                level2[i2] = self.disk.allocate_block()
                inode.blocks_used += 1
                self._write_pointers(level1[i1], level2)
            return level2[i2]

        # level == "triple"
        i1, i2, i3 = idx
        if inode.triple_indirect is None:
            inode.triple_indirect = self._new_pointer_block()
            inode.blocks_used += 1
        level1 = self._read_pointers(inode.triple_indirect)
        if level1[i1] == NULL_PTR:
            level1[i1] = self._new_pointer_block()
            inode.blocks_used += 1
            self._write_pointers(inode.triple_indirect, level1)
        level2 = self._read_pointers(level1[i1])
        if level2[i2] == NULL_PTR:
            level2[i2] = self._new_pointer_block()
            inode.blocks_used += 1
            self._write_pointers(level1[i1], level2)
        level3 = self._read_pointers(level2[i2])
        if level3[i3] == NULL_PTR:
            level3[i3] = self.disk.allocate_block()
            inode.blocks_used += 1
            self._write_pointers(level2[i2], level3)
        return level3[i3]

    # ------------------------------------------------------------------
    # Operacoes de arquivo (API publica)
    # ------------------------------------------------------------------
    def create_file(self, name: str, data: bytes) -> Inode:
        if name in self.directory:
            raise FileAlreadyExists(f"Arquivo '{name}' ja existe.")

        num_blocks_needed = max(1, math.ceil(len(data) / self.disk.block_size))
        if num_blocks_needed > self.max_blocks_per_file:
            raise FileTooLargeError(
                f"Arquivo de {len(data)} bytes precisa de {num_blocks_needed} blocos, "
                f"mas o maximo suportado e {self.max_blocks_per_file}."
            )

        inode = Inode(self._next_inode_num, self.D)
        self._next_inode_num += 1

        for logical_index in range(num_blocks_needed):
            phys = self._allocate_logical_block(inode, logical_index)
            start = logical_index * self.disk.block_size
            chunk = data[start: start + self.disk.block_size]
            self.disk.write_block(phys, chunk)

        inode.file_size_bytes = len(data)
        self.inodes[inode.inode_num] = inode
        self.directory[name] = inode.inode_num
        return inode

    def _get_inode(self, name: str) -> Inode:
        if name not in self.directory:
            raise FileNotFoundInFS(f"Arquivo '{name}' nao encontrado.")
        return self.inodes[self.directory[name]]

    def read_file(self, name: str, use_cache: bool = False) -> AccessResult:
        """Le o arquivo inteiro, bloco a bloco (varredura sequencial).

        use_cache=True simula um buffer/cache de blocos de ponteiros: o
        mesmo bloco indireto, ao ser acessado de novo para um bloco de
        dados vizinho, nao gera nova leitura fisica no disco.
        """
        inode = self._get_inode(name)
        num_blocks = max(1, math.ceil(inode.file_size_bytes / self.disk.block_size))

        cache: Dict[int, List[int]] = {}
        reads_before = self.disk.physical_reads
        out = bytearray()

        for logical_index in range(num_blocks):
            phys = self._resolve_for_read(inode, logical_index, cache if use_cache else None)
            block = self.disk.read_block(phys)
            out.extend(block)

        data = bytes(out[: inode.file_size_bytes])
        physical_reads = self.disk.physical_reads - reads_before
        return AccessResult(data=data, physical_disk_reads=physical_reads,
                             logical_block_accesses=num_blocks)

    def _resolve_for_read(self, inode: Inode, logical_index: int,
                           cache: Optional[Dict[int, List[int]]]) -> int:
        """Igual a _allocate_logical_block, mas somente para LEITURA (nao
        cria nada) e com suporte opcional a cache de blocos de ponteiros."""
        level, idx = self._locate(logical_index)

        def get_ptrs(block_idx: int) -> List[int]:
            if cache is not None and block_idx in cache:
                return cache[block_idx]
            ptrs = self._read_pointers(block_idx)
            if cache is not None:
                cache[block_idx] = ptrs
            return ptrs

        if level == "direct":
            (pos,) = idx
            return inode.direct[pos]

        if level == "single":
            (pos,) = idx
            ptrs = get_ptrs(inode.single_indirect)
            return ptrs[pos]

        if level == "double":
            i1, i2 = idx
            level1 = get_ptrs(inode.double_indirect)
            level2 = get_ptrs(level1[i1])
            return level2[i2]

        i1, i2, i3 = idx
        level1 = get_ptrs(inode.triple_indirect)
        level2 = get_ptrs(level1[i1])
        level3 = get_ptrs(level2[i2])
        return level3[i3]

    def delete_file(self, name: str) -> None:
        inode = self._get_inode(name)

        for ptr in inode.direct:
            if ptr is not None:
                self.disk.free_block(ptr)

        if inode.single_indirect is not None:
            self._free_pointer_subtree(inode.single_indirect, depth=1)
        if inode.double_indirect is not None:
            self._free_pointer_subtree(inode.double_indirect, depth=2)
        if inode.triple_indirect is not None:
            self._free_pointer_subtree(inode.triple_indirect, depth=3)

        del self.inodes[inode.inode_num]
        del self.directory[name]

    def _free_pointer_subtree(self, block_idx: int, depth: int) -> None:
        """Libera recursivamente um bloco de ponteiros e tudo que ele
        referencia. depth=1 -> os ponteiros sao para dados.
        depth=2/3 -> os ponteiros sao para outros blocos de ponteiros."""
        ptrs = self._read_pointers(block_idx)
        for p in ptrs:
            if p == NULL_PTR:
                continue
            if depth == 1:
                self.disk.free_block(p)
            else:
                self._free_pointer_subtree(p, depth - 1)
        self.disk.free_block(block_idx)

    # ------------------------------------------------------------------
    # Estatisticas / metricas por arquivo
    # ------------------------------------------------------------------
    def file_stats(self, name: str) -> dict:
        inode = self._get_inode(name)
        num_data_blocks = max(1, math.ceil(inode.file_size_bytes / self.disk.block_size))
        pointer_blocks = inode.blocks_used - num_data_blocks

        last_logical = num_data_blocks - 1
        level, _ = self._locate(last_logical)
        max_access_cost = self.access_cost(level)

        allocated_space = num_data_blocks * self.disk.block_size
        internal_fragmentation = allocated_space - inode.file_size_bytes

        return {
            "nome": name,
            "tamanho_bytes": inode.file_size_bytes,
            "blocos_de_dados": num_data_blocks,
            "blocos_de_ponteiros": pointer_blocks,
            "blocos_totais": inode.blocks_used,
            "nivel_max_indirecao": level,
            "acessos_max_a_disco": max_access_cost,
            "fragmentacao_interna_bytes": internal_fragmentation,
            "overhead_metadados_pct": round(100 * pointer_blocks / inode.blocks_used, 1)
            if inode.blocks_used else 0.0,
        }
