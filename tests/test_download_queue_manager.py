"""Testes unitarios para o modulo download_queue_manager.py."""

import unittest

from download_queue_manager import (
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_DOWNLOADING,
    STATUS_FAILED,
    STATUS_PENDING,
    DownloadQueueManager,
    QueueItem,
)


def item(url="https://youtube.com/watch?v=abc", **kwargs):
    """Cria um QueueItem com URL padrao para os testes."""
    return QueueItem(url=url, **kwargs)


# ─── QueueItem ───────────────────────────────────────────────────────────────


class TestQueueItem(unittest.TestCase):
    def test_valores_padrao(self):
        it = item()
        self.assertEqual(it.status, STATUS_PENDING)
        self.assertEqual(it.formato, "mp4")
        self.assertEqual(it.qualidade, "Melhor disponivel")
        self.assertEqual(it.titulo, "")
        self.assertEqual(it.erro, "")
        self.assertEqual(it.data_conclusao, "")
        self.assertIsNone(it.cookies)

    def test_campos_personalizados(self):
        it = item(formato="mp3", qualidade="HD (720p)", cookies="firefox",
                  subs=True, playlist_start=1, playlist_end=3)
        self.assertEqual(it.formato, "mp3")
        self.assertEqual(it.qualidade, "HD (720p)")
        self.assertEqual(it.cookies, "firefox")
        self.assertTrue(it.subs)
        self.assertEqual(it.playlist_start, 1)
        self.assertEqual(it.playlist_end, 3)

    def test_to_dict(self):
        it = item("https://exemplo.com/video")
        it.titulo = "Meu video"
        d = it.to_dict()
        self.assertEqual(d["url"], "https://exemplo.com/video")
        self.assertEqual(d["formato"], "MP4")  # maiusculo para exibicao
        self.assertEqual(d["titulo"], "Meu video")
        self.assertEqual(d["status"], STATUS_PENDING)
        self.assertTrue(d["data"])  # horario de adicao preenchido

    def test_to_dict_titulo_fallback_para_url(self):
        url = "https://exemplo.com/video-bem-longa-para-testar"
        d = item(url).to_dict()
        self.assertEqual(d["titulo"], url[:50])


# ─── Fila: adicionar / consultar ─────────────────────────────────────────────


class TestFilaBasica(unittest.TestCase):
    def setUp(self):
        self.fila = DownloadQueueManager()

    def test_add_retorna_indice(self):
        self.assertEqual(self.fila.add(item()), 0)
        self.assertEqual(self.fila.add(item()), 1)

    def test_total_count(self):
        self.assertEqual(self.fila.total_count(), 0)
        self.fila.add(item())
        self.fila.add(item())
        self.assertEqual(self.fila.total_count(), 2)

    def test_get_items_retorna_copia(self):
        self.fila.add(item())
        lista = self.fila.get_items()
        lista.clear()
        self.assertEqual(self.fila.total_count(), 1)

    def test_pending_count(self):
        self.fila.add(item())
        self.fila.add(item())
        self.fila.get_next()
        # 1 baixando + 1 pendente
        self.assertEqual(self.fila.get_pending_count(), 2)

    def test_add_notifica_status_change(self):
        chamadas = []
        self.fila.set_on_status_change(lambda: chamadas.append(1))
        self.fila.add(item())
        self.fila.add(item())
        self.assertGreaterEqual(len(chamadas), 2)

    def test_notify_sem_callback_nao_quebra(self):
        # Sem callbacks registrados, nenhuma operacao deve lancar excecao
        self.fila.add(item())
        self.fila.remove(0)
        self.fila.clear_all()


# ─── Processamento sequencial ────────────────────────────────────────────────


class TestProcessamento(unittest.TestCase):
    def setUp(self):
        self.fila = DownloadQueueManager()
        self.itens = [item(f"https://youtu.be/{i}") for i in range(3)]
        for it in self.itens:
            self.fila.add(it)

    def test_get_next_marca_como_downloading(self):
        prox = self.fila.get_next()
        self.assertIs(prox, self.itens[0])
        self.assertEqual(prox.status, STATUS_DOWNLOADING)
        self.assertTrue(self.fila.is_processing)

    def test_get_next_respeita_ordem(self):
        self.fila.get_next()
        self.fila.mark_completed(self.itens[0])
        self.assertIs(self.fila.get_next(), self.itens[1])

    def test_get_next_sem_pendentes(self):
        for it in self.itens:
            self.fila.get_next()
            self.fila.mark_completed(it)
        self.assertIsNone(self.fila.get_next())

    def test_get_current(self):
        self.fila.get_next()
        self.assertIs(self.fila.get_current(), self.itens[0])

    def test_get_current_sem_download(self):
        self.assertIsNone(self.fila.get_current())

    def test_mark_completed_sucesso(self):
        self.fila.get_next()
        self.fila.mark_completed(self.itens[0])
        self.assertEqual(self.itens[0].status, STATUS_COMPLETED)
        self.assertTrue(self.itens[0].data_conclusao)

    def test_mark_completed_falha(self):
        self.fila.get_next()
        self.fila.mark_completed(self.itens[0], sucesso=False)
        self.assertEqual(self.itens[0].status, STATUS_FAILED)

    def test_continua_processando_ate_o_fim(self):
        self.fila.get_next()
        self.fila.mark_completed(self.itens[0])
        self.assertTrue(self.fila.is_processing)  # ainda ha pendentes

    def test_fim_da_fila_encerra_processamento(self):
        self.fila.get_next()
        self.fila.mark_completed(self.itens[0])
        self.fila.get_next()
        self.fila.mark_completed(self.itens[1])
        self.fila.get_next()
        self.fila.mark_completed(self.itens[2])
        self.assertFalse(self.fila.is_processing)
        self.assertIsNone(self.fila.get_current())

    def test_callback_item_complete(self):
        chamadas = []
        self.fila.set_on_item_complete(
            lambda it, ok: chamadas.append((it.url, ok)))
        self.fila.get_next()
        self.fila.mark_completed(self.itens[0], sucesso=False)
        self.assertEqual(chamadas, [("https://youtu.be/0", False)])

    def test_callback_fila_concluida(self):
        concluida = []
        self.fila.set_on_queue_complete(lambda: concluida.append(1))
        for it in self.itens:
            self.fila.get_next()
            self.fila.mark_completed(it)
        self.assertEqual(concluida, [1])


# ─── Remocao e reordenacao ───────────────────────────────────────────────────


class TestRemocao(unittest.TestCase):
    def setUp(self):
        self.fila = DownloadQueueManager()
        self.itens = [item(f"https://youtu.be/{i}") for i in range(3)]
        for it in self.itens:
            self.fila.add(it)

    def test_remove(self):
        self.assertTrue(self.fila.remove(1))
        self.assertEqual(self.fila.total_count(), 2)
        self.assertIs(self.fila.get_items()[1], self.itens[2])

    def test_remove_indice_invalido(self):
        self.assertFalse(self.fila.remove(99))
        self.assertFalse(self.fila.remove(-1))

    def test_remove_bloqueado_enquanto_baixa(self):
        self.fila.get_next()  # item 0 fica downloading (indice 0)
        self.assertFalse(self.fila.remove(0))
        self.assertEqual(self.fila.total_count(), 3)

    def test_remove_depois_do_indice_atual_nao_ajusta(self):
        self.fila.get_next()      # current = 0
        self.fila.mark_completed(self.itens[0])
        self.fila.get_next()      # current = 1 (item 1)
        self.assertTrue(self.fila.remove(2))  # remove item depois do atual
        # current_index permanece 1; o item atual continua sendo itens[1]
        self.assertIs(self.fila.get_current(), self.itens[1])
        self.assertEqual(self.fila.total_count(), 2)

    def test_remove_ajusta_indice_atual(self):
        self.fila.get_next()      # current = 0
        self.fila.mark_completed(self.itens[0])
        self.fila.get_next()      # current = 1 (item 1)
        self.assertTrue(self.fila.remove(0))  # remove item antes do atual
        # O item atual (itens[1]) desce para o indice 0
        self.assertIs(self.fila.get_current(), self.itens[1])

    def test_move_up(self):
        self.assertTrue(self.fila.move_up(2))
        # O item do indice 2 sobe uma posicao (para o indice 1)
        self.assertIs(self.fila.get_items()[1], self.itens[2])
        self.assertIs(self.fila.get_items()[2], self.itens[1])

    def test_move_up_primeiro_item(self):
        self.assertFalse(self.fila.move_up(0))

    def test_move_down(self):
        self.assertTrue(self.fila.move_down(0))
        self.assertIs(self.fila.get_items()[0], self.itens[1])
        self.assertIs(self.fila.get_items()[1], self.itens[0])

    def test_move_down_ultimo_item(self):
        self.assertFalse(self.fila.move_down(2))


class TestRetry(unittest.TestCase):
    def setUp(self):
        self.fila = DownloadQueueManager()
        self.itens = [item(f"https://youtu.be/{i}") for i in range(3)]
        for it in self.itens:
            self.fila.add(it)

    def test_retry_item_falho(self):
        self.fila.get_next()
        self.fila.mark_completed(self.itens[0], sucesso=False)
        self.itens[0].erro = "algum erro"
        self.assertTrue(self.fila.retry(0))
        self.assertEqual(self.itens[0].status, STATUS_PENDING)
        self.assertEqual(self.itens[0].erro, "")
        self.assertEqual(self.itens[0].data_conclusao, "")

    def test_retry_item_cancelado(self):
        self.itens[1].status = STATUS_CANCELLED
        self.assertTrue(self.fila.retry(1))
        self.assertEqual(self.itens[1].status, STATUS_PENDING)

    def test_retry_nao_permitido(self):
        self.itens[0].status = STATUS_COMPLETED
        self.itens[1].status = STATUS_PENDING
        self.itens[2].status = STATUS_DOWNLOADING
        self.assertFalse(self.fila.retry(0))
        self.assertFalse(self.fila.retry(1))
        self.assertFalse(self.fila.retry(2))
        self.assertFalse(self.fila.retry(99))

    def test_retry_notifica_status(self):
        chamadas = []
        self.fila.set_on_status_change(lambda: chamadas.append(1))
        self.itens[0].status = STATUS_FAILED
        self.fila.retry(0)
        self.assertEqual(chamadas, [1])


class TestClear(unittest.TestCase):
    def setUp(self):
        self.fila = DownloadQueueManager()
        self.itens = [item(f"https://youtu.be/{i}") for i in range(3)]
        for it in self.itens:
            self.fila.add(it)

    def test_clear_mantem_apenas_o_atual(self):
        self.fila.get_next()  # item 0 baixando
        self.fila.clear()
        self.assertEqual(self.fila.total_count(), 1)
        self.assertIs(self.fila.get_items()[0], self.itens[0])

    def test_clear_com_fila_vazia(self):
        self.fila.clear_all()
        self.fila.clear()  # nao deve quebrar
        self.assertEqual(self.fila.total_count(), 0)

    def test_clear_all(self):
        self.fila.clear_all()
        self.assertEqual(self.fila.total_count(), 0)
        self.assertFalse(self.fila.is_processing)


# ─── Progresso ───────────────────────────────────────────────────────────────


class TestProgresso(unittest.TestCase):
    def setUp(self):
        self.fila = DownloadQueueManager()

    def test_fila_vazia(self):
        self.assertEqual(self.fila.progress_text, "")

    def test_sem_processamento(self):
        self.fila.add(item())
        self.fila.add(item())
        self.assertEqual(self.fila.progress_text, "0/2")

    def test_processando(self):
        self.fila.add(item())
        self.fila.add(item())
        self.fila.get_next()
        self.assertEqual(self.fila.progress_text, "1/2")

    def test_apos_concluir_um(self):
        it1 = item("https://youtu.be/1")
        it2 = item("https://youtu.be/2")
        self.fila.add(it1)
        self.fila.add(it2)
        self.fila.get_next()
        self.fila.mark_completed(it1)
        self.assertEqual(self.fila.progress_text, "2/2")


if __name__ == "__main__":
    unittest.main()
