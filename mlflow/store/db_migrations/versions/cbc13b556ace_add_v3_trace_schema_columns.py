"""add v3 trace schema columns

Revision ID: cbc13b556ace
Revises: 5b0e9adcef9c
Create Date: 2025-01-13 14:20:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "cbc13b556ace"
down_revision = "5b0e9adcef9c"
branch_labels = None
depends_on = None


def upgrade():
    """
    Migrate trace_info table from V2 to unified V3 schema.
    Uses field mapping approach for cleaner schema.
    """
    
    # Step 1: Add new V3 columns
    op.add_column("trace_info", sa.Column("trace_id_new", sa.String(255), nullable=True))
    op.add_column("trace_info", sa.Column("request_time", sa.BigInteger, nullable=True))
    op.add_column("trace_info", sa.Column("execution_duration", sa.BigInteger, nullable=True))
    op.add_column("trace_info", sa.Column("state", sa.String(50), nullable=True))
    op.add_column("trace_info", sa.Column("trace_location_type", sa.String(50), nullable=True))
    op.add_column("trace_info", sa.Column("trace_location_id", sa.String(255), nullable=True))
    op.add_column("trace_info", sa.Column("request_preview", sa.Text, nullable=True))
    op.add_column("trace_info", sa.Column("response_preview", sa.Text, nullable=True))
    op.add_column("trace_info", sa.Column("client_request_id", sa.String(255), nullable=True))
    
    # Step 2: Migrate existing V2 data to V3 format in batches
    connection = op.get_bind()
    batch_size = 1000
    
    while True:
        try:
            # Try PostgreSQL/SQLite style first
            result = connection.execute(
                text(f"""
                UPDATE trace_info SET 
                    trace_id_new = 'tr-' || request_id,
                    request_time = timestamp_ms,
                    execution_duration = execution_time_ms,
                    state = status,
                    trace_location_type = 'experiment',
                    trace_location_id = CAST(experiment_id AS TEXT),
                    client_request_id = request_id
                WHERE trace_id_new IS NULL 
                LIMIT {batch_size}
                """)
            )
        except Exception:
            # Fallback to MySQL style CONCAT
            result = connection.execute(
                text(f"""
                UPDATE trace_info SET 
                    trace_id_new = CONCAT('tr-', request_id),
                    request_time = timestamp_ms,
                    execution_duration = execution_time_ms,
                    state = status,
                    trace_location_type = 'experiment',
                    trace_location_id = CAST(experiment_id AS CHAR(255)),
                    client_request_id = request_id
                WHERE trace_id_new IS NULL 
                LIMIT {batch_size}
                """)
            )
        
        if result.rowcount == 0:
            break
    
    # Step 3: Make V3 columns non-nullable and set defaults
    with op.batch_alter_table("trace_info") as batch_op:
        batch_op.alter_column("trace_id_new", nullable=False)
        batch_op.alter_column("request_time", nullable=False)
        batch_op.alter_column("state", nullable=False)
        batch_op.alter_column("trace_location_type", nullable=False, server_default="experiment")
        batch_op.alter_column("trace_location_id", nullable=False)
    
    # Step 4: Drop old V2 columns and indexes
    op.drop_constraint("trace_info_pk", "trace_info", type_="primary")
    op.drop_index("index_trace_info_experiment_id_timestamp_ms", "trace_info")
    
    op.drop_column("trace_info", "request_id")
    op.drop_column("trace_info", "timestamp_ms")
    op.drop_column("trace_info", "execution_time_ms")
    op.drop_column("trace_info", "status")
    
    # Step 5: Rename trace_id_new to trace_id
    with op.batch_alter_table("trace_info") as batch_op:
        batch_op.alter_column("trace_id_new", new_column_name="trace_id")
    
    # Step 6: Create new primary key and indexes
    op.create_primary_key("trace_info_pk", "trace_info", ["trace_id"])
    op.create_index("index_trace_info_experiment_id_request_time", "trace_info", ["experiment_id", "request_time"])
    op.create_index("index_trace_info_trace_location", "trace_info", ["trace_location_type", "trace_location_id"])


def downgrade():
    """
    Revert unified V3 schema back to V2 schema.
    This is a destructive operation - V3-specific data will be lost.
    """
    # Step 1: Add back V2 columns
    op.add_column("trace_info", sa.Column("request_id", sa.String(50), nullable=True))
    op.add_column("trace_info", sa.Column("timestamp_ms", sa.BigInteger, nullable=True))
    op.add_column("trace_info", sa.Column("execution_time_ms", sa.BigInteger, nullable=True))
    op.add_column("trace_info", sa.Column("status", sa.String(50), nullable=True))
    
    # Step 2: Migrate V3 data back to V2 format
    connection = op.get_bind()
    connection.execute(
        text("""
        UPDATE trace_info SET 
            request_id = CASE 
                WHEN trace_id LIKE 'tr-%' THEN SUBSTR(trace_id, 4)
                ELSE trace_id
            END,
            timestamp_ms = request_time,
            execution_time_ms = execution_duration,
            status = state
        """)
    )
    
    # Step 3: Make V2 columns non-nullable
    with op.batch_alter_table("trace_info") as batch_op:
        batch_op.alter_column("request_id", nullable=False)
        batch_op.alter_column("timestamp_ms", nullable=False)
        batch_op.alter_column("status", nullable=False)
    
    # Step 4: Drop V3 constraints and indexes
    op.drop_constraint("trace_info_pk", "trace_info", type_="primary")
    op.drop_index("index_trace_info_trace_location", "trace_info")
    op.drop_index("index_trace_info_experiment_id_request_time", "trace_info")
    
    # Step 5: Drop V3 columns
    op.drop_column("trace_info", "client_request_id")
    op.drop_column("trace_info", "response_preview")
    op.drop_column("trace_info", "request_preview")
    op.drop_column("trace_info", "trace_location_id")
    op.drop_column("trace_info", "trace_location_type")
    op.drop_column("trace_info", "state")
    op.drop_column("trace_info", "execution_duration")
    op.drop_column("trace_info", "request_time")
    op.drop_column("trace_info", "trace_id")
    
    # Step 6: Restore V2 primary key and indexes
    op.create_primary_key("trace_info_pk", "trace_info", ["request_id"])
    op.create_index("index_trace_info_experiment_id_timestamp_ms", "trace_info", ["experiment_id", "timestamp_ms"])