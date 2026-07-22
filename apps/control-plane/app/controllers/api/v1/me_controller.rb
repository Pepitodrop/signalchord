module Api
  module V1
    # The single, canonical place the onboarding-state machine is computed —
    # ProtectedRoute (web) asks this once instead of reconstructing the same
    # rule from multiple separate API calls in TypeScript.
    #
    # In practice, reaching this action at all already guarantees the caller
    # is verified with an enabled membership (authenticate_api_token! only
    # ever issues/accepts a token for a verified user with a valid, enabled
    # membership) — so "verification_required" and "workspace_required" are
    # normally surfaced directly by the signup/login response bodies, not by
    # this endpoint. The full 4-state check is still evaluated here
    # defensively rather than assumed, so it self-corrects if that invariant
    # is ever violated by a future change elsewhere.
    class MeController < ApplicationController
      def show
        return render_error("not_found", :not_found) unless current_api_token.user_id

        user = User.find(current_api_token.user_id)
        render json: {
          user: user.as_json(only: %i[id email display_name]),
          organization: current_organization.as_json(only: %i[id name slug]),
          role: current_membership&.role,
          onboarding_state: onboarding_state_for(user)
        }
      end

      private

      def onboarding_state_for(user)
        return "verification_required" unless user.email_verified?
        return "workspace_required" unless user.memberships.enabled.exists?
        return "first_watchlist_required" unless current_organization.watchlists.exists?

        "complete"
      end
    end
  end
end
