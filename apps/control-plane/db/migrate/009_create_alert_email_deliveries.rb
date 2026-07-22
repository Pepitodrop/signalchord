class CreateAlertEmailDeliveries < ActiveRecord::Migration[8.0]
  def change
    create_table :alert_email_deliveries, id: :uuid do |t|
      t.references :organization, type: :uuid, null: false, foreign_key: true
      t.references :alert, type: :uuid, null: false, foreign_key: true
      t.references :membership, type: :uuid, null: false, foreign_key: true
      t.string :status, null: false, default: "pending"
      t.integer :attempts, null: false, default: 0
      t.text :last_error
      t.timestamps
    end
    add_index :alert_email_deliveries, %i[alert_id membership_id], unique: true, name: "idx_alert_email_delivery_dedup"
  end
end
