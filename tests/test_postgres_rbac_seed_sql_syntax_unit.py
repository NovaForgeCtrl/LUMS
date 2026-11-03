import re

from server.migrations.rbac_seed import RBAC_SEED_MIGRATION


def test_every_plpgsql_do_block_ends_with_semicolon():
    do_blocks = [
        statement
        for statement in RBAC_SEED_MIGRATION.statements
        if statement.lstrip().startswith("DO $lums$")
    ]

    assert len(do_blocks) == 6

    for index, statement in enumerate(do_blocks, start=1):
        assert statement.count("$lums$") == 2, (
            f"DO-Block {index}: Dollar-Quote ist nicht ausgeglichen"
        )
        assert re.search(
            r"\bEND;\s*\$lums\$\s*$",
            statement,
            flags=re.DOTALL,
        ), f"DO-Block {index}: PL/pgSQL-Blockabschluss END; fehlt"
