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
          email_alerts_enabled: current_membership&.email_alerts_enabled,
          onboarding_state: onboarding_state_for(user)
        }
      end

      # Scoped to current_membership only — resolved server-side from the
      # authenticated token, never from a client-supplied id — so this can
      # never update another user's membership regardless of request body.
      def update
        return render_error("not_found", :not_found) unless current_membership

        current_membership.update!(params.require(:membership).permit(:email_alerts_enabled))
        render json: { email_alerts_enabled: current_membership.email_alerts_enabled }
      end

      private

      def onboarding_state_for(user)
        return "verification_required" unless user.email_verified?
        return "workspace_required" unless user.memberships.enabled.exists?
        # An empty Watchlist shell (no items) doesn't satisfy onboarding —
        # the journey requires a real monitored subject, not just a name.
        # Single indexed EXISTS query via the join, no N+1.
        return "first_watchlist_required" unless current_organization.watchlists.joins(:watchlist_items).exists?

        "complete"
      end
    end
  end
end
