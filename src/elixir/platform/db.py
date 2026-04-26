from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def build_engine(database_url: str, **kwargs) -> AsyncEngine:
    return create_async_engine(
        database_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=kwargs.get("pool_size", 10),
        max_overflow=kwargs.get("max_overflow", 20),
        pool_recycle=kwargs.get("pool_recycle", 1800),   # recycle connections every 30 min
        pool_timeout=kwargs.get("pool_timeout", 30),      # wait max 30s for a connection
        connect_args={
            "command_timeout": kwargs.get("command_timeout", 30),  # asyncpg-specific: 30s statement timeout
            "server_settings": {
                "application_name": "elixir",
                "statement_timeout": str(kwargs.get("statement_timeout_ms", 30000)),
            },
        },
    )


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
