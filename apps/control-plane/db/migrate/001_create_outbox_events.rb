class CreateOutboxEvents < ActiveRecord::Migration[8.0]
  def change
    create_table :outbox_events, id: :uuid do |t|
      t.uuid :tenant_id, null: false
      t.string :topic, null: false
      t.string :partition_key, null: false
      t.string :event_type, null: false
      t.integer :schema_version, null: false, default: 1
      t.jsonb :payload, null: false
      t.string :correlation_id, null: false
      t.string :causation_id
      t.datetime :occurred_at, null: false
      t.datetime :published_at
      t.integer :publish_attempts, null: false, default: 0
      t.text :last_error
      t.timestamps
    end
    add_index :outbox_events, [:published_at, :created_at]
    add_index :outbox_events, [:tenant_id, :topic, :partition_key]
  end
end
