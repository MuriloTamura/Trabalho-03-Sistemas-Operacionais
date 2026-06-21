"""
inode.py
--------
Estrutura de i-node inspirada no Unix classico (V7 / ext2), com:

    - N ponteiros diretos          -> acesso a 1 bloco de dados
    - 1 ponteiro indireto simples  -> 1 bloco de ponteiros -> P blocos de dados
    - 1 ponteiro indireto duplo    -> bloco de ponteiros -> P blocos de
                                       ponteiros -> P blocos de dados cada
    - 1 ponteiro indireto triplo   -> mais um nivel de indirecao

Cada i-node guarda apenas METADADOS (tamanho do arquivo, numero de blocos
usados e os ponteiros). Os dados em si ficam nos blocos do VirtualDisk.
"""

from __future__ import annotations
from typing import List, Optional


class Inode:
    def __init__(self, inode_num: int, num_direct: int):
        self.inode_num = inode_num
        self.file_size_bytes = 0          # tamanho logico do arquivo
        self.blocks_used = 0              # total de blocos fisicos consumidos
                                           # (dados + blocos de ponteiros)

        # Ponteiros diretos: lista de tamanho fixo, None = nao alocado
        self.direct: List[Optional[int]] = [None] * num_direct

        # Ponteiros indiretos (cada um aponta para um bloco que contem
        # mais ponteiros, ou None se ainda nao alocado)
        self.single_indirect: Optional[int] = None
        self.double_indirect: Optional[int] = None
        self.triple_indirect: Optional[int] = None

    def __repr__(self) -> str:
        return (f"Inode(#{self.inode_num}, tamanho={self.file_size_bytes}B, "
                f"blocos_usados={self.blocks_used}, "
                f"diretos_ocupados={sum(1 for d in self.direct if d is not None)}, "
                f"single_indirect={'sim' if self.single_indirect is not None else 'nao'}, "
                f"double_indirect={'sim' if self.double_indirect is not None else 'nao'}, "
                f"triple_indirect={'sim' if self.triple_indirect is not None else 'nao'})")
