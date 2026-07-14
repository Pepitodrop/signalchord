module Api
  module V1
    class SourcesController < ApplicationController
      before_action -> { require_scope!("api:write") }, except: %i[index show]
      before_action :require_writable_account!, except: %i[index show]
      before_action :source, only: %i[show update destroy]

      def index = render json: current_organization.sources.order(:name)
      def show = render json: @source
      def create
        enforce_usage_limit!(:sources)
        record = current_organization.sources.create!(source_params)
        audit!(action: "source.created", target: record)
        render json: record, status: :created
      end
      def update
        @source.update!(source_params)
        audit!(action: "source.updated", target: @source)
        render json: @source
      end
      def destroy
        @source.update!(enabled: false)
        audit!(action: "source.disabled", target: @source)
        head :no_content
      end

      private

      def source = @source = current_organization.sources.find(params[:id])
      def source_params
        params.require(:source).permit(:name, :endpoint, :adapter, :rights_status, :enabled, :requests_per_minute, :raw_retention_days, policy_metadata: {})
      end
    end
  end
end
