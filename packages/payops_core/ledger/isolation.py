from sqlalchemy.engine import Connection, Engine

# SQLite writers take a reserved lock on the first write in the transaction.
# PostgreSQL uses SERIALIZABLE so two overlapping overdrafts cannot both commit.
# Do not pass isolation_level=IMMEDIATE through execution_options — the dialect
# rejects it. The IMMEDIATE label is the intended lock mode, issued as a raw BEGIN.
ISOLATION_SQLITE = "IMMEDIATE"
ISOLATION_POSTGRES = "SERIALIZABLE"


def isolation_for(engine: Engine) -> tuple[str, str]:
    if engine.dialect.name == "sqlite":
        return (
            ISOLATION_SQLITE,
            "SQLite reserved write lock: the debit/credit/ledger write is one "
            "transaction so a second transfer cannot persist a dirty or lost update "
            "on the same account.",
        )
    return (
        ISOLATION_POSTGRES,
        "PostgreSQL SERIALIZABLE: the debit/credit/ledger write is one serializable "
        "snapshot so concurrent overdrafts cannot both commit.",
    )


def connect_for_transfer(engine: Engine) -> tuple[Connection, str, str]:
    isolation, reason = isolation_for(engine)
    connection = engine.connect()
    if engine.dialect.name == "sqlite":
        return connection, isolation, reason
    return connection.execution_options(isolation_level=isolation), isolation, reason
