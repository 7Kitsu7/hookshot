import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# 1. IMPORTACION DE MODELOS
# Esto es vital para que 'autogenerate' detecte los cambios en las tablas
from app.db.session import Base
from app.models.subscription import Subscription
from app.models.delivery import EventPayload, DeliveryAttempt

# Este es el objeto de configuración de Alembic
config = context.config

# 2. CONFIGURACIÓN DINÁMICA DE LA URL
# Prioriza la variable de entorno DATABASE_URL definida en docker-compose
db_url = os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url"))
config.set_main_option("sqlalchemy.url", db_url)

# Configura el logeo básico
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 3. VINCULA LA METADATA DE TUS MODELOS 
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Ejecutar migraciones en modo 'offline'."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Ejecutar migraciones en modo 'online'."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()