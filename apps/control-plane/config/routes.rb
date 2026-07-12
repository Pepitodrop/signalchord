Rails.application.routes.draw do
  get "/healthz", to: "health#show"

  namespace :internal do
    namespace :v1 do
      resources :alerts, only: :create
      resource :token, only: :show
    end
  end

  namespace :api do
    namespace :v1 do
      post "auth/session", to: "auth#create"
      get :search, to: "search#show"
      resources :organizations, only: %i[index show]
      resources :sources
      resources :watchlists
      resources :investigations
      resources :alerts, only: %i[index show update]
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
