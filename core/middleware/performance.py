
import logging
import re
import time

from django.db import connection
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger("core.performance")


def _normalize_sql(sql: str) -> str:
    """Normalize SQL by removing literal values to find N+1 patterns."""
    # Replace quoted strings
    sql = re.sub(r"'[^']*'", "?", sql)
    # Replace numbers
    sql = re.sub(r"\b\d+\b", "?", sql)
    return sql

class PerformanceMiddleware(MiddlewareMixin):
    """Middleware para monitorizar performance das requests"""
    
    def process_request(self, request):
        request.start_time = time.time()
        request.db_queries_start = len(connection.queries)
    
    def process_response(self, request, response):
        if hasattr(request, 'start_time'):
            duration = time.time() - request.start_time
            db_queries = len(connection.queries) - getattr(request, 'db_queries_start', 0)
            
            # Log requests lentas
            if duration > 1.0:  # Mais de 1 segundo
                logger.warning(
                    f"Slow request: {request.method} {request.path} "
                    f"took {duration:.2f}s with {db_queries} DB queries"
                )
            
            # Log queries excessivas
            if db_queries > 10:
                logger.warning(
                    f"High DB usage: {request.method} {request.path} "
                    f"used {db_queries} queries in {duration:.2f}s"
                )

            # Detetar e registar possíveis N+1 queries
            queries = connection.queries[getattr(request, 'db_queries_start', 0):]
            normalized = {}
            for q in queries:
                sql = q.get("sql", "")
                norm = _normalize_sql(sql)
                normalized[norm] = normalized.get(norm, 0) + 1
            for sql, count in normalized.items():
                if count > 1:
                    logger.warning(
                        f"Potential N+1 query detected {count} times: {sql[:200]}"
                    )
            
            # Adicionar headers de performance em desenvolvimento
            if hasattr(request, 'user') and request.user.is_staff:
                response['X-DB-Queries'] = str(db_queries)
                response['X-Response-Time'] = f"{duration:.3f}s"
        
        return response
