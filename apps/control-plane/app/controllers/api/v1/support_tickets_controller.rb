module Api
  module V1
    class SupportTicketsController < ApplicationController
      before_action :ticket, only: %i[show update]

      def index
        scope = current_organization.support_tickets.order(created_at: :desc)
        render json: scope.limit([params.fetch(:limit, 100).to_i, 250].min)
      end

      def show
        render json: @ticket
      end

      def create
        raise Forbidden unless current_api_token.user_id

        record = current_organization.support_tickets.create!(
          ticket_params.merge(
            opened_by_user_id: current_api_token.user_id,
            contact_email: ticket_params[:contact_email].presence || current_membership.user.email
          )
        )
        audit!(action: "support_ticket.created", target: record, metadata: { severity: record.severity, category: record.category })
        render json: record, status: :created
      end

      def update
        require_role!("owner", "admin")
        @ticket.update!(ticket_params.slice(:status, :severity, :metadata))
        audit!(action: "support_ticket.updated", target: @ticket, metadata: ticket_params.slice(:status, :severity))
        render json: @ticket
      end

      private

      def ticket
        @ticket = current_organization.support_tickets.find(params[:id])
      end

      def ticket_params
        params.require(:support_ticket).permit(:subject, :category, :severity, :status, :contact_email, :description, metadata: {})
      end
    end
  end
end
