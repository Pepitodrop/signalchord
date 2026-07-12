Rails.application.routes.draw do
  namespace :api do
    namespace :v1 do
      resources :organizations
      resources :sources
      resources :watchlists
      resources :investigations
      resources :alerts, only: [:index, :show, :update]
      resources :policies do
        post :simulate, on: :member
        post :upload_velato, on: :member
      end
      resources :entities, only: [:show] do
        get :timeline, on: :member
        get :graph, on: :member
      end
    end
  end
end
