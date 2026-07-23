module Api
  module V1
    class MembershipsController < ApplicationController
      before_action -> { require_role!("owner", "admin") }
      before_action :membership, only: %i[update destroy]

      def index
        render json: current_organization.memberships.includes(:user).order(created_at: :asc).map { |record| serialize(record) }
      end

      def update
        attrs = membership_params
        was_enabled = @membership.disabled_at.nil?
        prevents_enabled_owner = @membership.role == "owner" && (
          (attrs[:role].present? && attrs[:role] != "owner") ||
          (attrs.key?(:disabled_at) && attrs[:disabled_at].present?)
        )
        prevent_last_owner_loss! if prevents_enabled_owner
        @membership.update!(attrs)
        revoke_active_tokens!(@membership.user_id) if was_enabled && @membership.disabled_at.present?
        audit!(action: "membership.updated", target: @membership, metadata: attrs)
        render json: serialize(@membership)
      end

      def destroy
        prevent_last_owner_loss! if @membership.role == "owner"
        @membership.update!(disabled_at: Time.current)
        revoke_active_tokens!(@membership.user_id)
        audit!(action: "membership.suspended", target: @membership, metadata: { user_id: @membership.user_id })
        head :no_content
      end

      private

      def membership
        @membership = current_organization.memberships.find(params[:id])
      end

      def membership_params
        permitted = params.require(:membership).permit(:role, :disabled)
        attrs = {}
        attrs[:role] = permitted[:role] if permitted.key?(:role)
        attrs[:disabled_at] = ActiveModel::Type::Boolean.new.cast(permitted[:disabled]) ? Time.current : nil if permitted.key?(:disabled)
        attrs
      end

      def prevent_last_owner_loss!
        owners = current_organization.memberships.enabled.where(role: "owner")
        raise Forbidden if owners.count <= 1 && owners.exists?(@membership.id)
      end

      # Closes Blocker #3: a membership disabled via #update (not just
      # #destroy) must not leave its existing token(s) usable.
      def revoke_active_tokens!(user_id)
        current_organization.api_tokens.where(user_id:).active.update_all(revoked_at: Time.current, updated_at: Time.current)
      end

      def serialize(record)
        record.as_json(only: %i[id role disabled_at created_at updated_at]).merge(
          user: record.user.as_json(only: %i[id email display_name disabled_at])
        )
      end
    end
  end
end
