module Api
  module V1
    class OrganizationsController < ApplicationController
      def index = render json: [organization_json(current_organization)]
      def show = render json: organization_json(current_organization)

      private

      def organization_json(organization)
        organization.as_json(only: %i[id name slug created_at updated_at])
      end
    end
  end
end
