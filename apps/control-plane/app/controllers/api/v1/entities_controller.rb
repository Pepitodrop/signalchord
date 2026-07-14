require "cgi"
require "net/http"

module Api
  module V1
    class EntitiesController < ApplicationController
      def show = proxy("/v1/entities/#{CGI.escape(stable_id)}")
      def timeline = proxy("/v1/entities/#{CGI.escape(stable_id)}/timeline", request.query_parameters)
      def graph = proxy("/v1/entities/#{CGI.escape(stable_id)}/graph", request.query_parameters)

      private

      def stable_id = params[:id] || params[:entity_id]

      def proxy(path, query = {})
        base = URI(ENV.fetch("GRAPH_QUERY_URL", "http://graph-query:8090"))
        uri = base + path
        uri.query = URI.encode_www_form(query.merge(tenant_id: current_organization.id)) if query.any? || current_organization
        response = Net::HTTP.get_response(uri)
        render body: response.body, status: response.code.to_i, content_type: response["content-type"] || "application/json"
      rescue StandardError => error
        Rails.logger.error(message: "graph query unavailable", error: error.class.name)
        render json: { error: "graph_query_unavailable" }, status: :service_unavailable
      end
    end
  end
end
