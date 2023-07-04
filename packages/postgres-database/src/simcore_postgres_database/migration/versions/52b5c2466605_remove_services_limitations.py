"""remove services_limitations

Revision ID: 52b5c2466605
Revises: 38fe651b4196
Create Date: 2023-06-27 15:24:13.207340+00:00

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "52b5c2466605"
down_revision = "38fe651b4196"
branch_labels = None
depends_on = None


modified_timestamp_trigger = sa.DDL(
    """
DROP TRIGGER IF EXISTS trigger_auto_update on services_limitations;
CREATE TRIGGER trigger_auto_update
BEFORE INSERT OR UPDATE ON services_limitations
FOR EACH ROW EXECUTE PROCEDURE services_limitations_auto_update_modified();
    """
)

update_modified_timestamp_procedure = sa.DDL(
    """
CREATE OR REPLACE FUNCTION services_limitations_auto_update_modified()
RETURNS TRIGGER AS $$
BEGIN
  NEW.modified := current_timestamp;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
    """
)


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index("idx_unique_gid_cluster_id_null", table_name="services_limitations")
    op.drop_table("services_limitations")
    # ### end Alembic commands ###
    # custom
    op.execute("DROP FUNCTION services_limitations_auto_update_modified();")


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "services_limitations",
        sa.Column("gid", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column("cluster_id", sa.BIGINT(), autoincrement=False, nullable=True),
        sa.Column("ram", sa.BIGINT(), autoincrement=False, nullable=True),
        sa.Column("cpu", sa.NUMERIC(), autoincrement=False, nullable=True),
        sa.Column("vram", sa.BIGINT(), autoincrement=False, nullable=True),
        sa.Column("gpu", sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column(
            "created",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "modified",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["cluster_id"],
            ["clusters.id"],
            name="fk_services_limitations_to_clusters_id",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["gid"],
            ["groups.gid"],
            name="fk_services_limitations_to_groups_gid",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("gid", "cluster_id", name="gid_cluster_id_uniqueness"),
    )
    op.create_index(
        "idx_unique_gid_cluster_id_null", "services_limitations", ["gid"], unique=False
    )
    # ### end Alembic commands ###

    # custom
    op.execute(update_modified_timestamp_procedure)
    op.execute(modified_timestamp_trigger)
