"""
test_filesystem.py
-------------------
Testes automatizados da simulacao de alocacao indexada por i-nodes.

Executar com:
    python3 -m pytest tests/ -v
ou:
    python3 -m unittest tests.test_filesystem -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from virtual_disk import VirtualDisk, DiskFullError
from filesystem import FileSystem, FileTooLargeError, FileAlreadyExists, FileNotFoundInFS


def make_fs(total_blocks=300, block_size=16, num_direct=4):
    disk = VirtualDisk(total_blocks=total_blocks, block_size=block_size)
    fs = FileSystem(disk, num_direct=num_direct)
    return disk, fs


class TestNiveisDeIndirecao(unittest.TestCase):
    """Garante que arquivos de tamanhos crescentes atravessam corretamente
    direto -> indireto simples -> indireto duplo -> indireto triplo."""

    def setUp(self):
        self.disk, self.fs = make_fs()

    def test_arquivo_cabe_apenas_em_blocos_diretos(self):
        dados = os.urandom(40)  # < D*block_size = 64
        self.fs.create_file("a.txt", dados)
        stats = self.fs.file_stats("a.txt")
        self.assertEqual(stats["nivel_max_indirecao"], "direct")
        self.assertEqual(stats["acessos_max_a_disco"], 1)

    def test_arquivo_exige_indireto_simples(self):
        dados = os.urandom(100)  # entre 64 e 128 bytes
        self.fs.create_file("b.txt", dados)
        stats = self.fs.file_stats("b.txt")
        self.assertEqual(stats["nivel_max_indirecao"], "single")
        self.assertEqual(stats["acessos_max_a_disco"], 2)

    def test_arquivo_exige_indireto_duplo(self):
        dados = os.urandom(300)  # entre 128 e 384 bytes
        self.fs.create_file("c.txt", dados)
        stats = self.fs.file_stats("c.txt")
        self.assertEqual(stats["nivel_max_indirecao"], "double")
        self.assertEqual(stats["acessos_max_a_disco"], 3)

    def test_arquivo_exige_indireto_triplo(self):
        dados = os.urandom(1200)  # entre 384 e 1408 bytes
        self.fs.create_file("d.txt", dados)
        stats = self.fs.file_stats("d.txt")
        self.assertEqual(stats["nivel_max_indirecao"], "triple")
        self.assertEqual(stats["acessos_max_a_disco"], 4)

    def test_arquivo_no_tamanho_maximo_exato(self):
        dados = os.urandom(self.fs.max_file_size_bytes)
        self.fs.create_file("max.txt", dados)
        lido = self.fs.read_file("max.txt")
        self.assertEqual(lido.data, dados)

    def test_arquivo_maior_que_o_maximo_levanta_erro(self):
        dados = os.urandom(self.fs.max_file_size_bytes + 1)
        with self.assertRaises(FileTooLargeError):
            self.fs.create_file("grande_demais.txt", dados)


class TestLeituraEEscrita(unittest.TestCase):
    def setUp(self):
        self.disk, self.fs = make_fs()

    def test_dados_lidos_sao_identicos_aos_escritos(self):
        for tamanho in [1, 16, 63, 64, 65, 127, 128, 300, 1000, 1408]:
            dados = os.urandom(tamanho)
            nome = f"arq_{tamanho}.bin"
            self.fs.create_file(nome, dados)
            resultado = self.fs.read_file(nome)
            self.assertEqual(resultado.data, dados, f"falhou para tamanho={tamanho}")

    def test_leitura_com_e_sem_cache_devolve_mesmos_dados(self):
        dados = os.urandom(1200)
        self.fs.create_file("e.txt", dados)
        sem_cache = self.fs.read_file("e.txt", use_cache=False)
        com_cache = self.fs.read_file("e.txt", use_cache=True)
        self.assertEqual(sem_cache.data, dados)
        self.assertEqual(com_cache.data, dados)
        # cache nunca deve gerar MAIS leituras fisicas que o modo sem cache
        self.assertLessEqual(com_cache.physical_disk_reads, sem_cache.physical_disk_reads)

    def test_criar_arquivo_com_nome_duplicado_levanta_erro(self):
        self.fs.create_file("dup.txt", b"abc")
        with self.assertRaises(FileAlreadyExists):
            self.fs.create_file("dup.txt", b"xyz")

    def test_ler_arquivo_inexistente_levanta_erro(self):
        with self.assertRaises(FileNotFoundInFS):
            self.fs.read_file("nao_existe.txt")


class TestRemocaoELiberacaoDeBlocos(unittest.TestCase):
    def setUp(self):
        self.disk, self.fs = make_fs()

    def test_remover_arquivo_libera_todos_os_blocos(self):
        dados = os.urandom(1200)  # exercita direto+simples+duplo+triplo
        self.fs.create_file("f.txt", dados)
        self.assertGreater(self.disk.used_blocks_count(), 0)
        self.fs.delete_file("f.txt")
        self.assertEqual(self.disk.used_blocks_count(), 0)
        self.assertEqual(self.disk.free_blocks_count(), self.disk.total_blocks)

    def test_remover_e_recriar_varios_arquivos_nao_gera_vazamento(self):
        nomes_tamanhos = [("x1", 10), ("x2", 90), ("x3", 350), ("x4", 1000)]
        for nome, tam in nomes_tamanhos:
            self.fs.create_file(nome, os.urandom(tam))
        for nome, _ in nomes_tamanhos:
            self.fs.delete_file(nome)
        self.assertEqual(self.disk.used_blocks_count(), 0)


class TestDiscoCheio(unittest.TestCase):
    def test_disco_sem_espaco_levanta_erro(self):
        disk, fs = make_fs(total_blocks=3, block_size=16, num_direct=4)
        # 3 blocos de dados cabem (todos diretos); o 4o exige espaco que nao existe
        with self.assertRaises(DiskFullError):
            fs.create_file("muito_grande.bin", os.urandom(16 * 10))


if __name__ == "__main__":
    unittest.main(verbosity=2)
