module Api
  module V1
    class InvitationsController < ApplicationController
      skip_before_action :authenticate_api_token!, only: :accept
      before_action -> { require_role!("owner", "admin") }, except: :accept
      before_action :require_writable_account!, except: %i[index accept]
      before_action :invitation, only: :destroy

      def index
        render json: current_organization.invitations.order(created_at: :desc).as_json(
          only: %i[id email role expires_at accepted_at revoked_at created_at]
        )
      end

      def create
        record, plaintext = Invitation.issue!(
          organization: current_organization,
          email: params.require(:email),
          role: params.require(:role),
          invited_by_user_id: current_api_token.user_id
        )
        audit!(action: "invitation.created", target: record, metadata: { email: record.email, role: record.role })
        render json: record.as_json(only: %i[id email role expires_at created_at]).merge(invitation_token: plaintext), status: :created
      end

      def destroy
        @invitation.update!(revoked_at: Time.current)
        audit!(action: "invitation.revoked", target: @invitation, metadata: { email: @invitation.email })
        head :no_content
      end

      def accept
        record = Invitation.authenticate(params.require(:invitation_token))
        return render json: { error: "invalid_invitation" }, status: :unauthorized unless record

        user = User.find_or_initialize_by(email: record.email)
        user.assign_attributes(
          password: params.require(:password),
          display_name: params[:display_name].presence || user.display_name || record.email
        )
        ActiveRecord::Base.transaction do
          user.save!
          membership = Membership.find_or_initialize_by(organization: record.organization, user:)
          membership.assign_attributes(role: record.role, disabled_at: nil)
          membership.save!
          record.update!(accepted_at: Time.current, accepted_by_user_id: user.id)
          record.organization.audit_events.create!(
            actor_user_id: user.id,
            action: "invitation.accepted",
            target_type: "Invitation",
            target_id: record.id,
            request_id: request.request_id,
            metadata: { role: record.role },
            occurred_at: Time.current
          )
        end
        token, plaintext = ApiToken.issue!(
          organization: record.organization,
          user:,
          name: "Session #{request.remote_ip}",
          scopes: scopes_for(record.role),
          expires_at: 30.days.from_now
        )
        render json: {
          access_token: plaintext,
          token_type: "Bearer",
          expires_at: token.expires_at,
          organization: record.organization.as_json(only: %i[id name slug]),
          user: user.as_json(only: %i[id email display_name]),
          role: record.role,
          scopes: token.scopes
        }, status: :created
      rescue ActiveRecord::RecordInvalid => error
        render json: { error: "validation_failed", details: error.record.errors.to_hash }, status: :unprocessable_entity
      end

      private

      def invitation
        @invitation = current_organization.invitations.where(accepted_at: nil).find(params[:id])
      end

      def scopes_for(role)
        case role
        when "admin" then ["*"]
        when "analyst", "reviewer" then %w[api:read api:write]
        else ["api:read"]
        end
      end
    end
  end
end
