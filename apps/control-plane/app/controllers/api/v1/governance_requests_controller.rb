module Api
  module V1
    class GovernanceRequestsController < ApplicationController
      before_action -> { require_scope!("api:write") }, only: :create
      before_action -> { require_role!("owner", "admin") }, only: :create
      before_action :governance_request, only: :show

      # Genuine concurrent double-submit with the same Idempotency-Key can
      # race past the new_record? check below (both requests see "not found
      # yet" before either commits). Re-fetch and return the now-committed
      # record as the idempotent replay would, rather than a raw 500 —
      # mirrors WatchlistsController's existing rescue.
      rescue_from ActiveRecord::RecordNotUnique, with: -> {
        existing = idempotency_key.present? ? current_organization.governance_requests.find_by(idempotency_key:) : nil
        existing ? (render json: existing, status: :ok) : render_error("conflict", :conflict)
      }

      def index
        render json: current_organization.governance_requests.order(created_at: :desc)
      end

      def show
        render json: @governance_request
      end

      def create
        record = current_organization.governance_requests.find_or_initialize_by(idempotency_key: idempotency_key)
        if record.new_record?
          record.assign_attributes(request_attributes)
          ActiveRecord::Base.transaction do
            apply_request!(record)
            record.save!
            audit!(action: "governance_request.created", target: record, metadata: record.parameters)
            publish_governance_event!(record)
          end
        end

        render json: record, status: record.previously_new_record? ? :created : :ok
      end

      private

      def governance_request
        @governance_request = current_organization.governance_requests.find(params[:id])
      end

      def idempotency_key
        request.headers["Idempotency-Key"].presence || params.require(:idempotency_key)
      end

      def request_attributes
        payload = params.require(:governance_request)
        {
          request_type: payload.require(:request_type),
          source_id: payload[:source_id],
          # `.fetch(:parameters, {})` (the prior form) wraps its OWN default
          # value through Parameters#convert_value_to_parameters, producing
          # an unpermitted Parameters object whenever `parameters` is absent
          # from the request — raising UnfilteredParameters on #to_h. `[]`
          # doesn't have that wrapping behavior for a missing key (just nil).
          parameters: payload.permit(parameters: {})[:parameters]&.to_h || {}
        }
      end

      def apply_request!(record)
        case record.request_type
        when "tenant_export"
          record.status = "completed"
          record.result = export_snapshot
        when "tenant_deletion"
          current_organization.sources.update_all(enabled: false, updated_at: Time.current)
          current_organization.alerts.update_all(suppressed: true, review_status: "deletion_pending", updated_at: Time.current)
          skipped_deliveries = current_organization.alert_email_deliveries.where(status: %w[pending sending])
                                                    .update_all(status: "skipped", last_error: "tenant_deletion_pending", updated_at: Time.current)
          record.status = "accepted"
          record.result = {
            "disabled_sources" => current_organization.sources.count,
            "suppressed_alerts" => current_organization.alerts.count,
            "skipped_alert_email_deliveries" => skipped_deliveries
          }
        when "source_takedown"
          source = current_organization.sources.find(record.source_id)
          source.update!(enabled: false, rights_status: "denied", policy_metadata: source.policy_metadata.merge("takedown_requested_at" => Time.current.iso8601, "takedown_reason" => record.parameters["reason"].presence || "unspecified"))
          record.result = { "source_id" => source.id, "status" => "disabled" }
        end
      end

      def export_snapshot
        {
          "organization" => current_organization.as_json(only: %i[id name slug plan created_at updated_at]),
          "sources" => current_organization.sources.order(:id).as_json(except: %i[organization_id]),
          "watchlists" => current_organization.watchlists.includes(:watchlist_items).order(:id).map { |watchlist|
            watchlist.as_json(except: %i[organization_id]).merge("items" => watchlist.watchlist_items.order(:id).as_json(except: %i[watchlist_id]))
          },
          "alerts" => current_organization.alerts.order(:id).as_json(except: %i[organization_id]),
          "alert_email_deliveries" => current_organization.alert_email_deliveries.order(:id).as_json(except: %i[organization_id]),
          "policies" => current_organization.policies.order(:id).as_json(except: %i[organization_id]),
          "investigations" => current_organization.investigations.order(:id).as_json(except: %i[organization_id]),
          "generated_at" => Time.current.iso8601
        }
      end

      def publish_governance_event!(record)
        topic = "#{record.request_type.tr("_", ".")}.requested.v1"
        OutboxEvent.enqueue!(
          organization: current_organization,
          topic:,
          partition_key: record.id,
          event_type: topic,
          payload: record.as_json(only: %i[id request_type source_id status parameters result created_at])
        )
        return unless record.request_type == "source_takedown"

        OutboxEvent.enqueue!(
          organization: current_organization,
          topic: "graph.mutation-requested.v1",
          partition_key: record.source_id,
          event_type: "graph.mutation-requested.v1",
          payload: {
            mutation_type: "mark_source_takedown",
            stable_id: record.source_id,
            properties: {
              governance_request_id: record.id,
              takedown_reason: record.parameters["reason"].presence || "unspecified",
              takedown_requested_at: record.created_at&.iso8601 || Time.current.iso8601
            }
          }
        )
      end
    end
  end
end
