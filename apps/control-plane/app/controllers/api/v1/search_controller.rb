require "net/http"
require "openssl"

module Api
  module V1
    class SearchController < ApplicationController
      INDEXES = %w[signalchord-articles signalchord-entities signalchord-claims].freeze

      def show
        query = params.require(:q).to_s.strip
        return render json: { results: [] } if query.blank?

        limit = [[params.fetch(:limit, 20).to_i, 1].max, 100].min
        results = INDEXES.flat_map { |index| search_index(index, query, limit) }
        render json: { query:, results: results.sort_by { |item| -item.fetch("score", 0).to_f }.first(limit) }
      end

      private

      def search_index(index, query, limit)
        base = URI(ENV.fetch("OPENSEARCH_URL", "http://opensearch:9200"))
        uri = base + "/#{index}/_search"
        request = Net::HTTP::Post.new(uri)
        request["Content-Type"] = "application/json"
        if ENV["OPENSEARCH_USERNAME"].present? && ENV["OPENSEARCH_PASSWORD"].present?
          request.basic_auth(ENV["OPENSEARCH_USERNAME"], ENV["OPENSEARCH_PASSWORD"])
        end
        request.body = JSON.generate(
          size: limit,
          query: {
            bool: {
              filter: [{ term: { tenant_id: current_organization.id } }],
              must: [{ multi_match: { query:, fields: ["title^3", "display_name^3", "proposition^2", "content"] } }]
            }
          }
        )
        response = Net::HTTP.start(uri.hostname, uri.port, use_ssl: uri.scheme == "https", read_timeout: 5) do |http|
          http.verify_mode = OpenSSL::SSL::VERIFY_PEER if uri.scheme == "https"
          http.request(request)
        end
        return [] unless response.is_a?(Net::HTTPSuccess)

        JSON.parse(response.body).dig("hits", "hits").to_a.map do |hit|
          { "index" => index, "id" => hit["_id"], "score" => hit["_score"], "source" => hit["_source"] }
        end
      rescue StandardError => error
        Rails.logger.warn(message: "search projection unavailable", index:, error: error.class.name)
        []
      end
    end
  end
end
