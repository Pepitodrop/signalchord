module Api
  module V1
    class OrganizationsController < ApplicationController
      include CookieSession

      # No pending session exists to authenticate this action (decision 5) —
      # it takes fresh email+password in the body and re-validates them
      # itself, exactly like a login. verify_same_origin! already no-ops for
      # any action that skips authenticate_api_token! (no @current_auth_source
      # is ever set), so nothing extra is needed there.
      skip_before_action :authenticate_api_token!, only: :create

      def index = render json: [organization_json(current_organization)]
      def show = render json: organization_json(current_organization)

      def create
        email = params.require(:email).to_s.strip.downcase
        password = params.require(:password).to_s
        name = params.require(:name).to_s

        user = User.find_by(email:)
        unless user&.authenticate(password) && !user.disabled?
          return render json: { error: "invalid_credentials" }, status: :unauthorized
        end
        return render json: { error: "verification_required" }, status: :forbidden unless user.email_verified?

        # This endpoint creates the ONE workspace during onboarding — it is
        # not a general "create additional orgs" endpoint (that's deferred,
        # see TODOS.md's org-picker entry for the multi-org future this
        # implies).
        if user.memberships.enabled.exists?
          return render json: { error: "already_has_workspace" }, status: :unprocessable_entity
        end

        organization = nil
        ActiveRecord::Base.transaction do
          organization = Organization.create!(name:, slug: unique_slug_for(name))
          membership = Membership.create!(organization:, user:, role: "owner")
          organization.audit_events.create!(
            actor_user_id: user.id,
            action: "organization.created",
            target_type: "Organization",
            target_id: organization.id,
            request_id: request.request_id,
            metadata: { via: "onboarding" },
            occurred_at: Time.current
          )
          organization.audit_events.create!(
            actor_user_id: user.id,
            action: "membership.created",
            target_type: "Membership",
            target_id: membership.id,
            request_id: request.request_id,
            metadata: { role: "owner" },
            occurred_at: Time.current
          )
        end

        token, plaintext = ApiToken.issue!(
          organization:,
          user:,
          name: "Web session #{request.remote_ip}",
          scopes: Membership.scopes_for("owner"),
          expires_at: 30.days.from_now
        )
        write_session_cookie(plaintext)
        render json: organization_json(organization).merge(role: "owner"), status: :created
      end

      private

      def organization_json(organization)
        organization.as_json(only: %i[id name slug created_at updated_at])
      end

      # Slug is derived, never typed by the user — a collision must never
      # surface as a validation error on a field they never saw. Bare slug
      # first, then -2, -3, ... until one is free.
      def unique_slug_for(name)
        base = name.to_s.strip.downcase.gsub(/[^a-z0-9]+/, "-").gsub(/\A-+|-+\z/, "")
        base = "workspace" if base.blank?

        slug = base
        attempt = 1
        while Organization.exists?(slug:)
          attempt += 1
          raise "unable to derive a unique organization slug after #{attempt} attempts" if attempt > 20

          slug = "#{base}-#{attempt}"
        end
        slug
      end
    end
  end
end
