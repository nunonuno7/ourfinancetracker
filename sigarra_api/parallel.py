"""Ferramentas de execução paralela com cache para o Sigarra.

Este módulo fornece:
- :func:`parallel_process` para execução paralela com *rate limiting* e *retries*.
- :func:`get_batch` que implementa o fluxo "cache-first, parallel-on-miss".

Ambas as funções exibem progresso através do `tqdm` quando disponível.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Iterable, Any, Dict, List, Tuple
import json
import os
import time

try:  # pragma: no cover - fallback simples
    from tqdm import tqdm
except Exception:  # pragma: no cover - sem dependencia pesada
    def tqdm(iterable, **kwargs):  # type: ignore
        return iterable


class SimpleCache:
    """Cache muito simples baseada em ficheiro JSON.

    Destina-se apenas a pequenos volumes de dados, evitando dependências
    externas. Chaves são convertidas em ``str`` para serialização JSON.
    """

    def __init__(self, path: str | None = None) -> None:
        self.path = path or os.path.join(os.path.dirname(__file__), "sigarra_cache.json")
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as fh:
                self.data: Dict[str, Any] = json.load(fh)
        else:
            self.data = {}

    def get(self, key: Any) -> Any | None:
        return self.data.get(str(key))

    def set(self, key: Any, value: Any) -> None:
        self.data[str(key)] = value
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh, ensure_ascii=False)


def _retry_call(func: Callable[[Any], Any], arg: Any, retries: int) -> Any:
    """Executa ``func`` com *retries* exponenciais em caso de erro."""
    for attempt in range(retries + 1):
        try:
            return func(arg)
        except Exception:  # pragma: no cover - dependente do utilizador
            if attempt == retries:
                raise
            time.sleep(0.5 * (2 ** attempt))


def parallel_process(
    items: Iterable[Any],
    worker: Callable[[Any], Any],
    *,
    max_workers: int = 5,
    rate_limit: float = 0.0,
    retries: int = 0,
    desc: str = "Processando",
) -> List[Any]:
    """Executa ``worker`` em paralelo sobre ``items``.

    Args:
        items: Iterável de argumentos a processar.
        worker: Função a aplicar a cada item.
        max_workers: Número máximo de *threads*.
        rate_limit: Tempo em segundos entre submissões (``0`` para ilimitado).
        retries: Número de tentativas em caso de exceção.
        desc: Descrição apresentada na barra de progresso.

    Returns:
        Lista de resultados na mesma ordem de ``items``.
    """
    items = list(items)
    results: List[Any] = [None] * len(items)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures: Dict[Any, Tuple[int, Any]] = {}
        for idx, item in enumerate(items):
            future = executor.submit(_retry_call, worker, item, retries)
            futures[future] = (idx, item)
            if rate_limit:
                time.sleep(rate_limit)
        for future in tqdm(as_completed(futures), total=len(futures), desc=desc):
            idx, _ = futures[future]
            results[idx] = future.result()
    return results


def get_batch(
    keys: Iterable[Any],
    fetch_one: Callable[[Any], Any],
    *,
    cache: SimpleCache | None = None,
    **parallel_kwargs: Any,
) -> Dict[Any, Any]:
    """Obtém dados em batch com estratégia "cache-first, parallel-on-miss".

    Args:
        keys: Identificadores a obter.
        fetch_one: Função que obtém um único item.
        cache: Instância de :class:`SimpleCache`. Quando ``None`` usa cache
            local no ficheiro ``sigarra_cache.json``.
        **parallel_kwargs: Argumentos adicionais passados para
            :func:`parallel_process` (ex.: ``max_workers`` ou ``retries``).

    Returns:
        Dicionário ``{key: dado}`` para todos os ``keys`` fornecidos.
    """
    cache = cache or SimpleCache()
    results: Dict[Any, Any] = {}
    missing: List[Any] = []
    for key in keys:
        cached = cache.get(key)
        if cached is not None:
            results[key] = cached
        else:
            missing.append(key)
    if missing:
        def worker(k: Any) -> Tuple[Any, Any]:
            return k, fetch_one(k)
        fetched = parallel_process(missing, worker, **parallel_kwargs)
        for key, value in fetched:
            results[key] = value
            cache.set(key, value)
    return results
