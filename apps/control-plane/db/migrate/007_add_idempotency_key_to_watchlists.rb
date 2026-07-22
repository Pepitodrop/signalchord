class AddIdempotencyKeyToWatchlists < ActiveRecord::Migration[8.0]
  def change
    add_column :watchlists, :idempotency_key, :string
    # Postgres unique indexes permit multiple NULL values natively (NULL is
    # never equal to another NULL under a unique constraint), so ordinary
    # non-keyed watchlist creates are unaffected by this index.
    add_index :watchlists, %i[organization_id idempotency_key], unique: true
  end
end
