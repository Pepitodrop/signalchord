class CreateGovernanceRequests < ActiveRecord::Migration[8.0]
  def change
    create_table :governance_requests, id: :uuid do |t|
      t.references :organization, type: :uuid, null: false, foreign_key: true
      t.uuid :source_id
      t.string :request_type, null: false
      t.string :idempotency_key, null: false
      t.string :status, null: false, default: "accepted"
      t.jsonb :parameters, null: false, default: {}
      t.jsonb :result, null: false, default: {}
      t.timestamps
    end

    add_index :governance_requests, %i[organization_id idempotency_key], unique: true, name: "idx_governance_request_idempotency"
    add_index :governance_requests, %i[organization_id request_type created_at], name: "idx_governance_request_type"
  end
end
