class AddEmailAlertsEnabledToMemberships < ActiveRecord::Migration[8.0]
  def change
    add_column :memberships, :email_alerts_enabled, :boolean, null: false, default: false
  end
end
