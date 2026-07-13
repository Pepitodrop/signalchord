class CreateControlPlane < ActiveRecord::Migration[8.0]
  def change
    create_table :organizations, id: :uuid do |t|
      t.string :name, null: false
      t.string :slug, null: false
      t.string :plan, null: false, default: "developer"
      t.jsonb :settings, null: false, default: {}
      t.timestamps
    end
    add_index :organizations, :slug, unique: true

    create_table :users, id: :uuid do |t|
      t.string :email, null: false
      t.string :password_digest, null: false
      t.string :display_name
      t.datetime :disabled_at
      t.timestamps
    end
    add_index :users, :email, unique: true

    create_table :memberships, id: :uuid do |t|
      t.references :organization, type: :uuid, null: false, foreign_key: true
      t.references :user, type: :uuid, null: false, foreign_key: true
      t.string :role, null: false, default: "analyst"
      t.timestamps
    end
    add_index :memberships, %i[organization_id user_id], unique: true

    create_table :api_tokens, id: :uuid do |t|
      t.references :organization, type: :uuid, null: false, foreign_key: true
      t.references :user, type: :uuid, null: true, foreign_key: true
      t.string :name, null: false
      t.string :token_digest, null: false
      t.jsonb :scopes, null: false, default: []
      t.datetime :last_used_at
      t.datetime :expires_at
      t.datetime :revoked_at
      t.timestamps
    end
    add_index :api_tokens, :token_digest, unique: true

    create_table :sources, id: :uuid do |t|
      t.references :organization, type: :uuid, null: false, foreign_key: true
      t.string :name, null: false
      t.string :endpoint, null: false
      t.string :adapter, null: false
      t.string :rights_status, null: false, default: "pending_review"
      t.boolean :enabled, null: false, default: false
      t.integer :requests_per_minute, null: false, default: 10
      t.integer :raw_retention_days, null: false, default: 30
      t.jsonb :policy_metadata, null: false, default: {}
      t.timestamps
    end
    add_index :sources, %i[organization_id endpoint], unique: true

    create_table :watchlists, id: :uuid do |t|
      t.references :organization, type: :uuid, null: false, foreign_key: true
      t.string :name, null: false
      t.text :description
      t.timestamps
    end

    create_table :watchlist_items, id: :uuid do |t|
      t.references :watchlist, type: :uuid, null: false, foreign_key: true
      t.string :target_kind, null: false
      t.string :target_stable_id, null: false
      t.decimal :relevance_weight, precision: 5, scale: 4, null: false, default: 1
      t.timestamps
    end
    add_index :watchlist_items, %i[watchlist_id target_stable_id], unique: true

    create_table :policies, id: :uuid do |t|
      t.references :organization, type: :uuid, null: false, foreign_key: true
      t.string :name, null: false
      t.text :description
      t.boolean :active, null: false, default: false
      t.jsonb :configuration, null: false, default: {}
      t.timestamps
    end

    create_table :policy_versions, id: :uuid do |t|
      t.references :policy, type: :uuid, null: false, foreign_key: true
      t.integer :version_number, null: false
      t.string :engine, null: false
      t.string :source_sha256
      t.string :ir_sha256
      t.string :status, null: false, default: "draft"
      t.binary :source_bytes, limit: 128_000
      t.text :decompiled_source
      t.jsonb :metadata, null: false, default: {}
      t.timestamps
    end
    add_index :policy_versions, %i[policy_id version_number], unique: true

    create_table :alerts, id: :uuid do |t|
      t.references :organization, type: :uuid, null: false, foreign_key: true
      t.references :policy, type: :uuid, null: true, foreign_key: true
      t.string :stable_id, null: false
      t.string :title, null: false
      t.text :summary
      t.integer :alert_score, null: false
      t.integer :severity_code, null: false
      t.integer :routing_code, null: false, default: 1
      t.boolean :suppressed, null: false, default: false
      t.jsonb :evidence_ids, null: false, default: []
      t.jsonb :graph_path_ids, null: false, default: []
      t.jsonb :policy_trace, null: false, default: {}
      t.string :review_status, null: false, default: "unreviewed"
      t.string :relevance_feedback
      t.datetime :read_at
      t.timestamps
    end
    add_index :alerts, %i[organization_id stable_id], unique: true

    create_table :investigations, id: :uuid do |t|
      t.references :organization, type: :uuid, null: false, foreign_key: true
      t.string :name, null: false
      t.text :description
      t.string :query_template
      t.jsonb :query_parameters, null: false, default: {}
      t.jsonb :graph_layout, null: false, default: {}
      t.jsonb :pinned_evidence_ids, null: false, default: []
      t.timestamps
    end

    create_table :audit_events, id: :uuid do |t|
      t.references :organization, type: :uuid, null: false, foreign_key: true
      t.uuid :actor_user_id
      t.string :action, null: false
      t.string :target_type, null: false
      t.uuid :target_id
      t.string :request_id
      t.jsonb :metadata, null: false, default: {}
      t.datetime :occurred_at, null: false
      t.timestamps
    end
    add_index :audit_events, %i[organization_id occurred_at]

    add_foreign_key :outbox_events, :organizations, column: :tenant_id
  end
end
