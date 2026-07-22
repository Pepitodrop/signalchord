Rails.application.routes.draw do
  get "/healthz", to: "health#show"

  namespace :internal do
    namespace :v1 do
      resources :alerts, only: :create
      resource :token, only: :show
      resources :notification_targets, only: %i[create update]
    end
  end

  namespace :api do
    namespace :v1 do
      post "auth/session", to: "auth#create"
      delete "auth/session", to: "sessions#destroy"
      resources :sessions, only: %i[index destroy]
      post "invitations/accept", to: "invitations#accept"
      get :search, to: "search#show"
      post "signup", to: "signups#create"
      post "email_verifications", to: "email_verifications#create"
      post "email_verifications/resend", to: "email_verifications#resend"
      post "auth/web_session", to: "web_sessions#create"
      delete "auth/web_session", to: "web_sessions#destroy"
      get "me", to: "me#show"
      patch "me", to: "me#update"
      resources :organizations, only: %i[index show create]
      resources :memberships, only: %i[index update destroy]
      resources :invitations, only: %i[index create destroy]
      resource :usage_limit, only: %i[show update]
      resources :support_tickets, only: %i[index show create update]
      resources :sources
      resources :watchlists
      resources :investigations
      resources :alerts, only: %i[index show update]
      resources :governance_requests, only: %i[index show create]
      resources :notification_endpoints, only: %i[index create destroy]
      resources :policies do
        post :simulate, on: :member
        post :upload_velato, on: :member
      end
      resources :entities, only: :show do
        get :timeline, on: :member
        get :graph, on: :member
      end
    end
  end
end
