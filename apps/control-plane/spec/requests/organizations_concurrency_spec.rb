require "rails_helper"

# Proves the pessimistic lock in OrganizationsController#create actually
# serializes two concurrent "does this user have a workspace yet" checks,
# rather than just asserting the code calls .lock (which would prove nothing
# about whether the race is actually closed under real concurrency).
#
# Needs real, separate DB connections to reproduce the race, so this disables
# the usual transactional-fixture rollback (which runs the whole example on
# one connection/transaction, making other threads unable to see committed
# data) and cleans up manually instead.
RSpec.describe "organizations#create concurrency", type: :request do
  self.use_transactional_fixtures = false

  after do
    Membership.delete_all
    Organization.delete_all
    User.delete_all
  end

  it "does not let two concurrent requests for the same user both create a workspace" do
    user = User.create!(email: "racer@example.com", password: "correct-horse-battery-staple", email_verified_at: Time.current)

    first_thread_holds_lock = Queue.new
    release_first_thread = Queue.new
    created_organization_ids = Array.new(2)

    # Thread A: acquire the row lock, then block until explicitly released,
    # simulating "still inside the transaction" for the race window.
    thread_a = Thread.new do
      ActiveRecord::Base.connection_pool.with_connection do
        ActiveRecord::Base.transaction do
          locked = User.lock.find(user.id)
          first_thread_holds_lock.push(true)
          release_first_thread.pop
          unless locked.memberships.enabled.exists?
            organization = Organization.create!(name: "Thread A Co", slug: "thread-a-co")
            Membership.create!(organization:, user: locked, role: "owner")
            created_organization_ids[0] = organization.id
          end
        end
      end
    end

    first_thread_holds_lock.pop # wait until thread A genuinely holds the lock

    thread_b = Thread.new do
      ActiveRecord::Base.connection_pool.with_connection do
        ActiveRecord::Base.transaction do
          # Blocks here until thread A's transaction commits (or rolls back)
          # and releases the row lock — this is the exact mechanism that
          # prevents the race in the real controller action.
          locked = User.lock.find(user.id)
          unless locked.memberships.enabled.exists?
            organization = Organization.create!(name: "Thread B Co", slug: "thread-b-co")
            Membership.create!(organization:, user: locked, role: "owner")
            created_organization_ids[1] = organization.id
          end
        end
      end
    end

    sleep 0.2 # give thread B a moment to actually start blocking on the lock
    release_first_thread.push(true)
    thread_a.join(5)
    thread_b.join(5)

    expect(created_organization_ids.compact.size).to eq(1)
    expect(user.reload.memberships.enabled.count).to eq(1)
  end
end
