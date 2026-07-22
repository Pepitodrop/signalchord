class CreateBetaOnboarding < ActiveRecord::Migration[8.0]
  def change
    change_table :users do |t|
      t.datetime :email_verified_at
      t.datetime :verification_email_sent_at
    end
  end
end
