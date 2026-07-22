module Api
  module V1
    class WatchlistsController < ApplicationController
      before_action -> { require_scope!("api:write") }, except: %i[index show]
      before_action :require_writable_account!, except: %i[index show]
      before_action :watchlist, only: %i[show update destroy]

      # A genuine concurrent double-submit with the same Idempotency-Key can
      # race past the new_record? check below (both requests see "not found
      # yet" before either commits). Re-fetch and return the now-committed
      # record as the idempotent replay would, rather than a raw 500 or a
      # conflict the client would just retry into the same race again.
      rescue_from ActiveRecord::RecordNotUnique, with: -> {
        existing = idempotency_key.present? ? current_organization.watchlists.find_by(idempotency_key:) : nil
        existing ? (render json: serialize(existing), status: :ok) : render_error("conflict", :conflict)
      }

      def index = render json: current_organization.watchlists.includes(:watchlist_items).map { |record| serialize(record) }
      def show = render json: serialize(@watchlist)

      # Idempotency is optional and backward compatible: with no
      # Idempotency-Key, this behaves exactly as before (always creates,
      # 201). With a key, replaying the same key returns the original
      # record (200) instead of creating a duplicate — same structural
      # pattern as GovernanceRequest (find_or_initialize_by + new_record?
      # guard around all side effects + previously_new_record? for status).
      def create
        enforce_usage_limit!(:watchlists)
        record = idempotency_key.present? ? current_organization.watchlists.find_or_initialize_by(idempotency_key:) : current_organization.watchlists.new

        if record.new_record?
          ActiveRecord::Base.transaction do
            record.assign_attributes(watchlist_params.except(:items))
            record.save!
            replace_items(record, watchlist_params[:items])
            audit!(action: "watchlist.created", target: record)
          end
        end

        render json: serialize(record), status: record.previously_new_record? ? :created : :ok
      end
      def update
        @watchlist.update!(watchlist_params.except(:items))
        replace_items(@watchlist, watchlist_params[:items]) if watchlist_params.key?(:items)
        audit!(action: "watchlist.updated", target: @watchlist)
        render json: serialize(@watchlist)
      end
      def destroy
        audit!(action: "watchlist.deleted", target: @watchlist)
        @watchlist.destroy!
        head :no_content
      end

      private

      def idempotency_key
        request.headers["Idempotency-Key"].presence || params[:idempotency_key].presence
      end

      def watchlist = @watchlist = current_organization.watchlists.find(params[:id])
      def watchlist_params
        params.require(:watchlist).permit(:name, :description, items: %i[target_kind target_stable_id relevance_weight])
      end
      def replace_items(record, items)
        return if items.nil?
        record.transaction do
          record.watchlist_items.delete_all
          Array(items).each { |item| record.watchlist_items.create!(item) }
        end
      end
      def serialize(record)
        record.as_json(only: %i[id name description created_at updated_at]).merge(items: record.watchlist_items.as_json(only: %i[id target_kind target_stable_id relevance_weight]))
      end
    end
  end
end
