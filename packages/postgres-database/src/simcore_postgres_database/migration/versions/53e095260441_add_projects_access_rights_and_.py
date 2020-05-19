"""add projects access rights and ownership to user id

Revision ID: 53e095260441
Revises: 64614dc0fada
Create Date: 2020-04-24 06:30:31.689985+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "53e095260441"
down_revision = "64614dc0fada"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "projects",
        sa.Column(
            "access_rights",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    # op.execute("UPDATE projects SET access_rights = {}")
    # op.alter_column("projects", "access_rights", nullable=False)
    op.alter_column("projects", "creation_date", server_default=sa.text("now()"))
    # FIXME: this does not work, alembic has no onupdate
    op.alter_column(
        "projects",
        "last_change_date",
        server_default=sa.text("now()"),
        # onupdate=sa.text("now()"),
    )
    # define conversion fct
    set_prj_owner_conversion_fct = sa.DDL(
        f"""
CREATE OR REPLACE FUNCTION convert_prj_owner_fct(current character varying)
  RETURNS BIGINT AS
$BODY$
SELECT id FROM users WHERE "email" = current

$BODY$
  LANGUAGE 'sql' IMMUTABLE STRICT;
        """
    )
    op.execute(set_prj_owner_conversion_fct)
    op.alter_column(
        "projects",
        "prj_owner",
        type_=sa.BigInteger,
        nullable=True,
        postgresql_using="convert_prj_owner_fct(prj_owner)",
        # postgresql_using="prj_owner::bigint",
    )
    op.execute("DROP FUNCTION convert_prj_owner_fct(current character varying)")
    op.create_foreign_key(
        "fk_projects_prj_owner_users",
        "projects",
        "users",
        ["prj_owner"],
        ["id"],
        onupdate="CASCADE",
        ondelete="RESTRICT",
    )

    op.execute(
        "UPDATE projects SET access_rights = '{\"1\":\"rwx\"}'::jsonb WHERE projects.type = 'TEMPLATE'"
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint("fk_projects_prj_owner_users", "projects", type_="foreignkey")
    set_prj_owner_conversion_fct = sa.DDL(
        f"""
CREATE OR REPLACE FUNCTION convert_prj_owner_fct(current BIGINT)
  RETURNS varchar AS
$BODY$
SELECT email FROM users WHERE "id" = current

$BODY$
  LANGUAGE 'sql' IMMUTABLE STRICT;
        """
    )
    op.execute(set_prj_owner_conversion_fct)
    op.alter_column(
        "projects",
        "prj_owner",
        type_=sa.String,
        nullable=False,
        postgresql_using="convert_prj_owner_fct(prj_owner)",
        # postgresql_using="prj_owner::bigint",
    )
    op.execute("DROP FUNCTION convert_prj_owner_fct(current BIGINT)")
    op.alter_column("projects", "prj_owner", type_=sa.String)
    op.alter_column(
        "projects",
        "last_change_date",
        server_default=None,
        # onupdate=None,
    )
    op.alter_column("projects", "creation_date", server_default=None)
    op.drop_column("projects", "access_rights")
    # ### end Alembic commands ###