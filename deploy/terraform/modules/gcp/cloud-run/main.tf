resource "google_cloud_run_service" "service" {
  name     = var.service_name
  location = var.region

  template {
    spec {
      containers {
        image = var.image_name

        # SRE Best Practice: Resource Limits
        resources {
          limits = {
            cpu    = "1000m"
            memory = "512Mi"
          }
        }

        # Inject Environment Variables
        env {
          name  = "ENV"
          value = var.environment
        }
      }

      # Reliability Settings
      container_concurrency = 80
      timeout_seconds       = 300
    }

    metadata {
      annotations = {
        # Scale to Zero (Cost Savings) & Circuit Breaker (Max Scale)
        "autoscaling.knative.dev/minScale" = "0"
        "autoscaling.knative.dev/maxScale" = "10"
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }
}

# IAM Member to allow public access (Invoke)
resource "google_cloud_run_service_iam_member" "public_access" {
  count    = var.allow_public_access ? 1 : 0
  service  = google_cloud_run_service.service.name
  location = google_cloud_run_service.service.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
