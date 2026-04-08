"""API utilitária para integração com o Sigarra.

Este módulo expõe funções para chamadas em batch com cache e execução paralela.
"""

from .parallel import parallel_process, get_batch

__all__ = ["parallel_process", "get_batch"]
