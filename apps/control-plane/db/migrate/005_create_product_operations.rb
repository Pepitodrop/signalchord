class CreateProductOperations < ActiveRecord::Migration[8.0]
  def change
    change_table :memberships do |t|
      t.datetime :disabled_at
    end

    create_table :invitations, id: :uuid do |t|
      t.references :organization, type: :uuid, null: false, foreign_key: true
      t.string :email, null: false
      t.string :role, null: false
      t.string :token_digest, null: false
      t.uuid :invited_by_user_id, null: false
      t.uuid :accepted_by_user_id
      t.datetime :expires_at, null: false
      t.datetime :accepted_at
      t.datetime :revoked_at
      t.timestamps
    end
    add_index :invitations, :token_digest, unique: true
    add_index :invitations, %i[organization_id email accepted_at revoked_at], name: "idx_invitations_org_email_state"

    create_table :usage_limits, id: :uuid do |t|
      t.references :organization, type: :uuid, null: false, foreign_key: true
      t.string :billing_state, null: false, default: "trialing"
      t.integer :source_limit, null: false, default: 5
      t.integer :watchlist_limit, null: false, default: 10
      t.integer :notification_endpoint_limit, null: false, default: 5
      t.integer :monthly_api_request_limit, null: false, default: 10_000
      t.jsonb :metadata, null: false, default: {}
      t.timestamps
    end
    add_index :usage_limits, :organization_id, unique: true

    create_table :support_tickets, id: :uuid do |t|
      t.references :organization, type: :uuid, null: false, foreign_key: true
      t.uuid :opened_by_user_id, null: false
      t.string :subject, null: false
      t.string :category, null: false, default: "support"
      t.string :severity, null: false, default: "normal"
      t.string :status, null: false, default: "open"
      t.string :contact_email, null: false
      t.text :description
      t.jsonb :metadata, null: false, default: {}
      t.timestamps
    end
    add_index :support_tickets, %i[organization_id status created_at], name: "idx_support_tickets_org_status"
  end
end
