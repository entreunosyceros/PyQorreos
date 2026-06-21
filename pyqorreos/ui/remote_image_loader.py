"""
Carga paralela de imágenes remotas con QThreadPool.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from pyqorreos.core.email_html import MAX_REMOTE_IMAGES
from pyqorreos.core.remote_image_cache import resolve_remote_image

MAX_REMOTE_IMAGE_WORKERS = 6


class _ResultEmitter(QObject):
    ready = Signal(int, str, str, bool)


class _LoadRemoteImageTask(QRunnable):
    def __init__(
        self,
        url: str,
        referer: str,
        generation: int,
        emitter: _ResultEmitter,
        loader: RemoteImageLoader,
    ) -> None:
        super().__init__()
        self.setAutoDelete(True)
        self._url = url
        self._referer = referer
        self._generation = generation
        self._emitter = emitter
        self._loader = loader

    def run(self) -> None:
        if not self._loader.is_generation_active(self._generation):
            return
        result = resolve_remote_image(self._url, referer=self._referer)
        if not self._loader.is_generation_active(self._generation):
            return
        if result:
            data_url, _from_cache = result
            self._emitter.ready.emit(
                self._generation, self._url, data_url, True
            )
        else:
            self._emitter.ready.emit(self._generation, self._url, "", False)


class RemoteImageLoader(QObject):
    """Descarga imágenes remotas en paralelo y emite cada resultado."""

    image_loaded = Signal(str, str)
    finished = Signal(int, int)
    progress = Signal(int, int)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(MAX_REMOTE_IMAGE_WORKERS)
        self._emitter = _ResultEmitter(self)
        self._emitter.ready.connect(self._on_result)
        self._active_generation = 0
        self._pending = 0
        self._loaded = 0
        self._failed = 0

    def is_generation_active(self, generation: int) -> bool:
        return generation >= 0 and generation == self._active_generation

    @Slot(int, str, str, bool)
    def _on_result(
        self, generation: int, url: str, data_url: str, success: bool
    ) -> None:
        if not self.is_generation_active(generation):
            return
        if success:
            self._loaded += 1
            self.image_loaded.emit(url, data_url)
        else:
            self._failed += 1
        self._pending -= 1
        done = self._loaded + self._failed
        total = done + self._pending
        self.progress.emit(done, total)
        if self._pending <= 0:
            self.finished.emit(self._loaded, self._failed)

    def invalidate(self) -> None:
        """Cancela descargas en curso y encoladas."""
        self._active_generation = -1
        self._pending = 0
        self._loaded = 0
        self._failed = 0
        self._pool.clear()

    def start(self, urls: list[str], *, referer: str, generation: int) -> int:
        """
        Encola descargas para las URLs indicadas.

        Devuelve cuántas tareas se encolaron (las ya en caché deben
        aplicarse antes en el hilo de la UI).
        """
        self._pool.clear()
        self._active_generation = generation
        unique = urls[:MAX_REMOTE_IMAGES]
        self._pending = len(unique)
        self._loaded = 0
        self._failed = 0
        if not unique:
            self.finished.emit(0, 0)
            return 0
        for url in unique:
            self._pool.start(
                _LoadRemoteImageTask(
                    url, referer, generation, self._emitter, self
                )
            )
        return len(unique)
