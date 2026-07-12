module Api
  module V1
    class InvestigationsController < ApplicationController
      before_action -> { require_scope!("api:write") }, except: %i[index show]
      before_action :investigation, only: %i[show update destroy]

      def index = render json: current_organization.investigations.order(updated_at: :desc)
      def show = render json: @investigation
      def create
        record = current_organization.investigations.create!(investigation_params)
        audit!(action: "investigation.created", target: record)
        render json: record, status: :created
      end
      def update
        @investigation.update!(investigation_params)
        audit!(action: "investigation.updated", target: @investigation)
        render json: @investigation
      end
      def destroy
        audit!(action: "investigation.deleted", target: @investigation)
        @investigation.destroy!
        head :no_content
      end

      private

      def investigation = @investigation = current_organization.investigations.find(params[:id])
      def investigation_params = params.require(:investigation).permit(:name, :description, :query_template, query_parameters: {}, graph_layout: {}, pinned_evidence_ids: [])
    end
  end
end
