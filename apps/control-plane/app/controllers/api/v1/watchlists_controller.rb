module Api
  module V1
    class WatchlistsController < ApplicationController
      before_action -> { require_scope!("api:write") }, except: %i[index show]
      before_action :require_writable_account!, except: %i[index show]
      before_action :watchlist, only: %i[show update destroy]

      def index = render json: current_organization.watchlists.includes(:watchlist_items).map { |record| serialize(record) }
      def show = render json: serialize(@watchlist)
      def create
        enforce_usage_limit!(:watchlists)
        record = current_organization.watchlists.create!(watchlist_params.except(:items))
        replace_items(record, watchlist_params[:items])
        audit!(action: "watchlist.created", target: record)
        render json: serialize(record), status: :created
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
