# Shared tenant-isolation matrix for org-scoped CRUD resources — replaces
# the previously scattered one-off "does this leak?" checks with a single
# parameterized set of examples, included once per resource controller.
#
# Including spec must define (via `let`/`let!`):
#   owner_headers    — auth headers for a token scoped to the OWNING org, with
#                       enough role/scope to read/write the resource
#   own_record       — an instance of the resource belonging to that org
#   other_record     — an instance of the SAME resource type belonging to a
#                       DIFFERENT org
#   index_path       — string path to the resource's #index
#   show_path        — proc: id -> path string for #show
#   update_path      — proc: id -> path string for #update
#   update_params    — params hash to send on the write-by-id attempt
RSpec.shared_examples "a tenant-isolated resource" do
  it "never includes another tenant's row in the list" do
    get index_path, headers: owner_headers

    ids = JSON.parse(response.body).map { |row| row.fetch("id") }
    expect(ids).to include(own_record.id)
    expect(ids).not_to include(other_record.id)
  end

  it "returns 404 (not another tenant's row) when reading by a guessed id" do
    get show_path.call(other_record.id), headers: owner_headers

    expect(response).to have_http_status(:not_found)
    expect(response.body).not_to include(other_record.id)
  end

  it "returns 404 and does not mutate another tenant's row when writing by a guessed id" do
    original_attributes = other_record.reload.attributes

    patch update_path.call(other_record.id), params: update_params, headers: owner_headers

    expect(response).to have_http_status(:not_found)
    expect(other_record.reload.attributes).to eq(original_attributes)
  end
end
