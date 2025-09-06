pipeline {
  agent any
  options {
    timestamps()
  }

  parameters {
    booleanParam(name: 'PRELOAD_TO_MINIKUBE', defaultValue: false,
      description: 'If true, preload the built image into Minikube (no registry pull); otherwise pull from Docker Hub.')
  }

  environment {
    DOCKER_IMG  = "itaysass/flask-redis-hello"   // <user>/<repo>
    CHART_DIR   = "helm/itaysass-flask"          // path to chart root
    CHART_VER   = "0.1.2"                        // chart version in Chart.yaml
    RELEASE     = "demo"                         // Helm release name
    // CHARTMUSEUM_URL is discovered dynamically at runtime
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
        powershell 'git rev-parse --short HEAD'
      }
    }

    stage('Compute tag') {
      steps {
        script {
          def sha = powershell(returnStdout: true, script: 'git rev-parse --short HEAD').trim()
          env.DOCKER_TAG = sha ?: env.BUILD_NUMBER
          echo "Using DOCKER_IMG=${env.DOCKER_IMG}"
          echo "Using DOCKER_TAG=${env.DOCKER_TAG}"
        }
      }
    }

    stage('Ensure Minikube up & context') {
      steps {
        powershell '''
          $ErrorActionPreference = "Stop"

          # Start if needed
          $status = (minikube status --output json) 2>$null
          if (!$status -or ($status -notmatch '"Host":\\s*"Running"')) {
            Write-Host "Starting Minikube (docker driver)…"
            minikube start --driver=docker --memory=4096 --cpus=2
          } else {
            Write-Host "Minikube already running."
          }

          # Point kubectl at Minikube
          $env:KUBECONFIG = "$env:USERPROFILE\\.kube\\config"
          minikube update-context | Out-Null
          kubectl cluster-info
          kubectl get nodes -o wide
        '''
      }
    }

    stage('Discover ChartMuseum URL') {
      steps {
        script {
          def url = powershell(returnStdout: true, script: '''
            $ErrorActionPreference = "Stop"
            $env:KUBECONFIG = "$env:USERPROFILE\\.kube\\config"
            $ns  = "chartmuseum"
            $svc = "cm-chartmuseum"

            for ($i=0; $i -lt 30; $i++) {
              try {
                $out = & minikube service -n $ns $svc --url 2>$null
                if ($LASTEXITCODE -eq 0 -and $out) {
                  $u = ($out -split "\\r?\\n" | Where-Object { $_ -match '^https?://' })[0]
                  if ($u) { $u.Trim(); exit 0 }
                }
              } catch { }
              Start-Sleep -Seconds 2
            }

            throw "Failed to resolve ChartMuseum URL via 'minikube service -n $ns $svc --url'"
          ''').trim()
          if (!url) { error 'ChartMuseum URL not found' }
          env.CHARTMUSEUM_URL = url
          echo "CHARTMUSEUM_URL=${env.CHARTMUSEUM_URL}"
        }
      }
    }

    stage('Docker login / build / push') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'DockerHubPass',
                                          usernameVariable: 'DH_USER',
                                          passwordVariable: 'DH_PASS')]) {
          retry(2) {
            powershell '''
              $ErrorActionPreference = "Stop"

              if ($env:DOCKER_IMG -notmatch '^[^/]+/[^/]+$') { throw "DOCKER_IMG must be <user>/<repo>" }
              if (-not $env:DH_USER -or -not $env:DH_PASS) { throw "Missing DH_USER/DH_PASS" }
              if (-not $env:DOCKER_TAG) { throw "Missing DOCKER_TAG" }

              Write-Host "Docker logout (best-effort)…"
              docker logout *>$null

              # Write password/token with NO trailing newline, then feed it to docker
              $pwdFile = [System.IO.Path]::GetTempFileName()
              Set-Content -Path $pwdFile -Value $env:DH_PASS -NoNewline -Encoding ASCII

              try {
                Write-Host "Docker login as $env:DH_USER"
                docker login -u "$env:DH_USER" --password-stdin < $pwdFile
                if ($LASTEXITCODE -ne 0) { throw "Docker login failed" }
              } finally {
                Remove-Item -Path $pwdFile -Force -ErrorAction SilentlyContinue
              }

              Write-Host "Building image $env:DOCKER_IMG:$env:DOCKER_TAG"
              docker build -f docker/Dockerfile -t "$env:DOCKER_IMG:$env:DOCKER_TAG" .

              Write-Host "Tagging also as latest"
              docker tag "$env:DOCKER_IMG:$env:DOCKER_TAG" "$env:DOCKER_IMG:latest"

              Write-Host "Pushing $env:DOCKER_IMG:$env:DOCKER_TAG"
              docker push "$env:DOCKER_IMG:$env:DOCKER_TAG"

              Write-Host "Pushing $env:DOCKER_IMG:latest"
              docker push "$env:DOCKER_IMG:latest"
            '''
          }
        }
      }
    }

    stage('(Optional) Preload image into Minikube') {
      when { expression { return params.PRELOAD_TO_MINIKUBE } }
      steps {
        powershell '''
          $ErrorActionPreference = "Stop"
          if (-not $env:DOCKER_TAG) { throw "Missing DOCKER_TAG" }

          $env:KUBECONFIG = "$env:USERPROFILE\\.kube\\config"
          $img = "itaysass/flask-redis-hello:$env:DOCKER_TAG"
          Write-Host "Preloading $img into Minikube…"
          minikube image load $img
          minikube image ls | Select-String $img | Out-Host
        '''
      }
    }

    stage('Lint & Package Helm chart') {
      steps {
        powershell '''
          $ErrorActionPreference = "Stop"
          if (-not (Test-Path $env:CHART_DIR)) { throw "Chart dir not found: $env:CHART_DIR" }

          Write-Host "Lint chart at $env:CHART_DIR"
          helm lint $env:CHART_DIR

          Write-Host "Package chart version $env:CHART_VER with appVersion $env:DOCKER_TAG"
          helm package $env:CHART_DIR --version $env:CHART_VER --app-version $env:DOCKER_TAG --destination .
        '''
      }
    }

    stage('Publish chart to ChartMuseum') {
      steps {
        powershell '''
          $ErrorActionPreference = "Stop"
          $file = "itaysass-flask-" + $env:CHART_VER + ".tgz"
          if (-not (Test-Path $file)) {
            $pkg = Get-ChildItem itaysass-flask-*.tgz | Sort-Object LastWriteTime | Select-Object -Last 1
            if (-not $pkg) { throw "Chart package (*.tgz) not found" }
            $file = $pkg.Name
          }

          Write-Host "Uploading chart: $file to $env:CHARTMUSEUM_URL"
          try {
            Invoke-WebRequest -Uri "$env:CHARTMUSEUM_URL/api/charts" -Method Post -InFile $file -ContentType "application/gzip" -UseBasicParsing | Out-Null
            Write-Host "Upload OK"
          } catch {
            $status = $_.Exception.Response.StatusCode.value__
            if ($status -eq 409) {
              Write-Host "Chart version already exists; continuing."
            } else {
              throw "Upload failed (HTTP $status): $($_.Exception.Message)"
            }
          }
        '''
      }
    }

    stage('Deploy/Upgrade via Helm') {
      steps {
        script {
          def pullPolicy = params.PRELOAD_TO_MINIKUBE ? 'IfNotPresent' : 'Always'
          withEnv([
            "KUBECONFIG=${env.USERPROFILE}\\.kube\\config",
            "PULL_POLICY=${pullPolicy}"
          ]) {
            retry(2) {
              powershell '''
                $ErrorActionPreference = "Stop"

                # Point a Helm repo at the discovered ChartMuseum URL
                helm repo remove itay-cm 2>$null
                helm repo add itay-cm $env:CHARTMUSEUM_URL | Out-Null
                helm repo update

                Write-Host "Deploying release $env:RELEASE with image tag $env:DOCKER_TAG (pullPolicy=$env:PULL_POLICY)"
                helm upgrade --install $env:RELEASE itay-cm/itaysass-flask `
                  --version $env:CHART_VER `
                  --set image.repository=$env:DOCKER_IMG `
                  --set image.tag=$env:DOCKER_TAG `
                  --set image.pullPolicy=$env:PULL_POLICY

                kubectl rollout status deployment/$env:RELEASE-flask --timeout=180s
              '''
            }
          }
        }
      }
    }
  }

  post {
    always {
      powershell '''
        $ErrorActionPreference = "Continue"
        $env:KUBECONFIG = "$env:USERPROFILE\\.kube\\config"

        Write-Host "`n=== Objects Summary ==="
        kubectl get deploy,rs,pod,svc,hpa,cm,secret -o wide 2>&1 | Write-Host

        Write-Host "`n=== Events (recent) ==="
        kubectl get events --sort-by=.lastTimestamp | Select-Object -Last 50 | Out-String | Write-Host

        Write-Host "`n=== Describe Deployment (demo-flask assumed) ==="
        kubectl describe deploy demo-flask 2>$null | Out-String | Write-Host

        Write-Host "`n=== Logs (deployment) ==="
        kubectl logs deploy/demo-flask --all-containers --tail=200 2>$null | Out-String | Write-Host
      '''
    }
  }
}
