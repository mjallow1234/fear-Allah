"""Form Builder - Dynamic Forms System

Revision ID: 022
Revises: 021
Create Date: 2026-01-05

Creates the Form Builder system for dynamic, admin-defined forms.
Forms define data structure - not business logic.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '022'
down_revision = '021'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enums
    op.execute("CREATE TYPE formfieldtype AS ENUM ('text', 'number', 'date', 'datetime', 'select', 'multiselect', 'checkbox', 'textarea', 'hidden')")
    op.execute("CREATE TYPE formcategory AS ENUM ('order', 'sale', 'inventory', 'raw_material', 'production', 'custom')")
    
    # =========================================
    # FORMS TABLE
    # =========================================
    op.create_table(
        'forms',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('slug', sa.String(100), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.Enum('order', 'sale', 'inventory', 'raw_material', 'production', 'custom', name='formcategory', create_type=False), nullable=False),
        sa.Column('allowed_roles', sa.Text(), nullable=True),  # JSON array
        sa.Column('service_target', sa.String(100), nullable=True),
        sa.Column('field_mapping', sa.Text(), nullable=True),  # JSON
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('current_version', sa.Integer(), default=1),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug', name='uq_forms_slug')
    )
    op.create_index('ix_forms_id', 'forms', ['id'])
    op.create_index('ix_forms_slug', 'forms', ['slug'])
    op.create_index('ix_forms_category', 'forms', ['category'])
    op.create_index('ix_forms_is_active', 'forms', ['is_active'])
    
    # =========================================
    # FORM FIELDS TABLE
    # =========================================
    op.create_table(
        'form_fields',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('form_id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(100), nullable=False),
        sa.Column('label', sa.String(255), nullable=False),
        sa.Column('field_type', sa.Enum('text', 'number', 'date', 'datetime', 'select', 'multiselect', 'checkbox', 'textarea', 'hidden', name='formfieldtype', create_type=False), nullable=False),
        sa.Column('placeholder', sa.String(255), nullable=True),
        sa.Column('help_text', sa.Text(), nullable=True),
        sa.Column('required', sa.Boolean(), default=False),
        sa.Column('min_value', sa.Integer(), nullable=True),
        sa.Column('max_value', sa.Integer(), nullable=True),
        sa.Column('min_length', sa.Integer(), nullable=True),
        sa.Column('max_length', sa.Integer(), nullable=True),
        sa.Column('pattern', sa.String(500), nullable=True),
        sa.Column('options', sa.Text(), nullable=True),  # JSON
        sa.Column('options_source', sa.String(255), nullable=True),
        sa.Column('default_value', sa.Text(), nullable=True),  # JSON
        sa.Column('role_visibility', sa.Text(), nullable=True),  # JSON
        sa.Column('conditional_visibility', sa.Text(), nullable=True),  # JSON
        sa.Column('order_index', sa.Integer(), default=0),
        sa.Column('field_group', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['form_id'], ['forms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_form_fields_id', 'form_fields', ['id'])
    op.create_index('ix_form_fields_form_id', 'form_fields', ['form_id'])
    op.create_index('ix_form_fields_key', 'form_fields', ['key'])
    
    # =========================================
    # FORM VERSIONS TABLE
    # =========================================
    op.create_table(
        'form_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('form_id', sa.Integer(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('snapshot', sa.Text(), nullable=False),  # JSON
        sa.Column('change_notes', sa.Text(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['form_id'], ['forms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_form_versions_id', 'form_versions', ['id'])
    op.create_index('ix_form_versions_form_id', 'form_versions', ['form_id'])
    op.create_index('ix_form_versions_version', 'form_versions', ['version'])
    
    # =========================================
    # FORM SUBMISSIONS TABLE
    # =========================================
    op.create_table(
        'form_submissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('form_id', sa.Integer(), nullable=False),
        sa.Column('form_version', sa.Integer(), nullable=False),
        sa.Column('data', sa.Text(), nullable=False),  # JSON
        sa.Column('service_target', sa.String(100), nullable=True),
        sa.Column('result_id', sa.Integer(), nullable=True),
        sa.Column('result_type', sa.String(50), nullable=True),
        sa.Column('status', sa.String(50), default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('submitted_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['form_id'], ['forms.id']),
        sa.ForeignKeyConstraint(['submitted_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_form_submissions_id', 'form_submissions', ['id'])
    op.create_index('ix_form_submissions_form_id', 'form_submissions', ['form_id'])
    op.create_index('ix_form_submissions_submitted_by_id', 'form_submissions', ['submitted_by_id'])
    op.create_index('ix_form_submissions_created_at', 'form_submissions', ['created_at'])


def downgrade() -> None:
    op.drop_table('form_submissions')
    op.drop_table('form_versions')
    op.drop_table('form_fields')
    op.drop_table('forms')
    op.execute("DROP TYPE IF EXISTS formfieldtype")
    op.execute("DROP TYPE IF EXISTS formcategory")
