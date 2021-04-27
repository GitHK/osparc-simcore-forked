"""adds file_meta_data.is_soft_link column

Revision ID: be29dbed0cce
Revises: e43bd59a8e17
Create Date: 2021-04-15 08:10:50.878539+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'be29dbed0cce'
down_revision = 'e43bd59a8e17'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('file_meta_data', sa.Column('is_soft_link', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('file_meta_data', 'is_soft_link')
    # ### end Alembic commands ###
