"""Small startup migrations for deployments without Alembic."""

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncConnection


async def migrate_user_credentials(connection: AsyncConnection) -> None:
    """Add auth columns to databases created before account authentication."""

    def existing_columns(sync_connection) -> set[str]:
        inspector = inspect(sync_connection)
        if "user_profiles" not in inspector.get_table_names():
            return set()
        return {column["name"] for column in inspector.get_columns("user_profiles")}

    columns = await connection.run_sync(existing_columns)
    if not columns:
        return
    if "username" not in columns:
        await connection.exec_driver_sql(
            "ALTER TABLE user_profiles ADD COLUMN username VARCHAR(64)"
        )
    if "password_hash" not in columns:
        await connection.exec_driver_sql(
            "ALTER TABLE user_profiles ADD COLUMN password_hash VARCHAR(255)"
        )
    await connection.exec_driver_sql(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_user_profiles_username "
        "ON user_profiles (username)"
    )
