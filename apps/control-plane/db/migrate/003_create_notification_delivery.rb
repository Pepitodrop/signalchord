class CreateNotificationDelivery < ActiveRecord::Migration[8.0]
  def change
    create_table :notification_endpoints, id: :uuid do |t|
      t.references :organization, type: :uuid, null: false, foreign_key: true
      t.references :user, type: :uuid, null: false, foreign_key: true
      t.string :platform, null: false
      t.string :token_digest, null: false
      t.text :token_ciphertext, null: false
      t.boolean :enabled, null: false, default: true
      t.datetime :last_seen_at
      t.timestamps
    end
    add_index :notification_endpoints, %i[organization_id token_digest], unique: true

    create_table :notification_deliveries, id: :uuid do |t|
      t.references :organization, type: :uuid, null: false, foreign_key: true
      t.references :notification_endpoint, type: :uuid, null: false, foreign_key: true
      t.string :event_id, null: false
      t.string :alert_id, null: false
      t.string :status, null: false, default: "pending"
      t.integer :attempts, null: false, default: 0
      t.string :provider_message_id
      t.text :last_error
      t.timestamps
    end
    add_index :notification_deliveries, %i[notification_endpoint_id event_id], unique: true, name: "idx_notification_delivery_idempotency"
  end
end
