"""Container package

이 패키지는 애플리케이션 전체 의존성 주입 컨테이너를 제공한다.

실제 구현 파일:
    core/container/container.py

외부 사용 예:
    from core.container import container

    settings = container.settings()
    db_local_service = container.db_local_service()
    remote_db_service = container.remote_db_service()
    scheduler_service = container.scheduler_service()
"""

from core.container.container import Container, container


__all__ = [
    "Container",
    "container",
]