"""Adds column to use scicrunch alternative

Revision ID: b60363fe438f
Revises: 39fa67f45cc0
Create Date: 2020-12-15 18:26:25.552123+00:00

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b60363fe438f"
down_revision = "39fa67f45cc0"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "group_classifiers",
        sa.Column("uses_scicrunch", sa.Boolean(), nullable=False, default=False),
    )
    # ### end Alembic commands ###

    # Applies the default to all
    query = 'UPDATE "group_classifiers" SET uses_scicrunch=false;'
    op.execute(query)
    # makes non nullable
    query = 'ALTER TABLE "group_classifiers" ALTER "uses_scicrunch" SET NOT NULL;'
    op.execute(query)


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("group_classifiers", "uses_scicrunch")
    # ### end Alembic commands ###