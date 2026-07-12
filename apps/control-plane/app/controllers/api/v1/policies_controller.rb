require "base64"
require "digest"
require "net/http"

module Api
  module V1
    class PoliciesController < ApplicationController
      before_action -> { require_scope!("api:write") }, except: %i[index show simulate]
      before_action -> { require_role!("owner", "admin") }, only: %i[create update destroy upload_velato]
      before_action :policy, only: %i[show update destroy simulate upload_velato]

      def index = render json: current_organization.policies.includes(:policy_versions).as_json(include: { policy_versions: { except: :source_bytes, methods: :source_size } })
      def show = render json: @policy.as_json(include: { policy_versions: { except: :source_bytes, methods: :source_size } })

      def create
        record = current_organization.policies.create!(policy_params)
        audit!(action: "policy.created", target: record)
        render json: record, status: :created
      end

      def update
        @policy.update!(policy_params)
        audit!(action: "policy.updated", target: @policy)
        render json: @policy
      end

      def destroy
        @policy.update!(active: false)
        audit!(action: "policy.disabled", target: @policy)
        head :no_content
      end

      def upload_velato
        bytes = Base64.strict_decode64(params.require(:midi_base64))
        raise ActionController::BadRequest, "MIDI exceeds limit" if bytes.bytesize > 128_000

        validation = validate_velato(bytes)
        version = @policy.policy_versions.create!(
          version_number: next_version,
          engine: "velato",
          source_sha256: Digest::SHA256.hexdigest(bytes),
          ir_sha256: validation.fetch("ir_sha256"),
          status: "validated",
          source_bytes: bytes,
          decompiled_source: validation.fetch("decompiled"),
          metadata: validation.slice("instruction_count", "note_count", "compiler_version")
        )
        OutboxEvent.enqueue!(
          organization: current_organization,
          topic: "audit.event.v1",
          partition_key: version.id,
          event_type: "policy.version-validated.v1",
          payload: { policy_id: @policy.id, policy_version_id: version.id, source_sha256: version.source_sha256, ir_sha256: version.ir_sha256 }
        )
        audit!(action: "policy.version_uploaded", target: version)
        render json: version.as_json(except: :source_bytes, methods: :source_size), status: :accepted
      rescue ArgumentError
        render json: { error: "invalid_midi_base64" }, status: :unprocessable_entity
      rescue VelatoValidationError => error
        render json: { error: "invalid_velato_program", detail: error.message }, status: :unprocessable_entity
      end

      def simulate
        inputs = params.require(:inputs).permit!.to_h.transform_values(&:to_f)
        version = @policy.policy_versions.where(status: "validated").order(version_number: :desc).first
        result = simulate_velato(version, inputs)
        render json: result.merge(policy_id: @policy.id, policy_version_id: version&.id, deterministic: true)
      rescue VelatoValidationError => error
        render json: { error: "policy_simulation_failed", detail: error.message }, status: :unprocessable_entity
      end

      private

      VelatoValidationError = Class.new(StandardError)

      def policy = @policy = current_organization.policies.find(params[:id])
      def policy_params = params.require(:policy).permit(:name, :description, :active, configuration: {})
      def next_version = (@policy.policy_versions.maximum(:version_number) || 0) + 1

      def velato_request(path, payload)
        base = URI(ENV.fetch("VELATO_ENGINE_URL", "http://velato-api:8091"))
        uri = base + path
        request = Net::HTTP::Post.new(uri)
        request["Content-Type"] = "application/json"
        request.body = JSON.generate(payload)
        response = Net::HTTP.start(uri.hostname, uri.port, use_ssl: uri.scheme == "https", read_timeout: 5, open_timeout: 2) { |http| http.request(request) }
        parsed = JSON.parse(response.body)
        raise VelatoValidationError, parsed["detail"] || "Velato engine rejected the program" unless response.is_a?(Net::HTTPSuccess)

        parsed
      rescue JSON::ParserError, Errno::ECONNREFUSED, Net::OpenTimeout, Net::ReadTimeout => error
        raise VelatoValidationError, "Velato engine unavailable: #{error.class.name}"
      end

      def validate_velato(bytes)
        velato_request("/v1/validate", { midi_base64: Base64.strict_encode64(bytes) })
      end

      def simulate_velato(version, inputs)
        payload = { inputs: }
        payload[:midi_base64] = Base64.strict_encode64(version.source_bytes) if version&.source_bytes.present?
        velato_request("/v1/simulate", payload)
      end
    end
  end
end
