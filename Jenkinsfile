pipeline {
  agent any
  options { timestamps() }

  environment {
    // App & chart
    DOCKER_IMG       = "itaysass/flask-redis-hello"     // <user>/<repo>
    CHART_DIR        = "helm/itaysass-flask"            // path to chart root
    CHART_VER        = "0.1.2"                          // chart version in Chart.yaml
    RELEASE          = "demo"                           // Helm release name

    // Infra
    CHARTMUSEUM_URL  = "http://127.0.0.1:64706"         // ChartMuseum base URL
    KUBECONFIG       = "${env.USERPROFILE}\\.kube\\config"

    // Docker Hub creds (creates DOCKER_CREDS_USR / DOCKER_CREDS_PSW)
    DOCKER_CREDS     = credentials('dockerhub-creds-2')
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

    stage('Docker login / build / push (latest only)') {
      steps {
        powershell '''
          $ErrorActionPreference = "Stop"

          $user = $env:DOCKER_CREDS_USR
          $pass = $env:DOCKER_CREDS_PSW
          if (-not $user -or -not $pass) { throw "Credential envs missing" }

          if ($env:DOCKER_IMG -notmatch '^[^/]+/[^/]+$') { throw "DOCKER_IMG must be <user>/<repo> (got: '$($env:DOCKER_IMG)')" }
          $full = "$($env:DOCKER_IMG):latest"

          Write-Host "Docker logout (best-effort)…"
          docker logout *>$null

          Write-Host "Docker login as $user"
          $pass | docker login -u $user --password-stdin
          if ($LASTEXITCODE -ne 0) { throw "Docker login failed" }

          Write-Host "Building $full"
          docker build -f docker/Dockerfile -t "$full" .

          Write-Host "Pushing $full"
          docker push "$full"
        '''
      }
    }

    stage('Package Helm chart') {
      steps {
        powershell '''
          $ErrorActionPreference = "Stop"
          if (-not (Test-Path $env:CHART_DIR)) { throw "Chart dir not found: $env:CHART_DIR" }

          Write-Host "Lint chart at $env:CHART_DIR"
          helm lint $env:CHART_DIR

          Write-Host "Package chart version $env:CHART_VER with appVersion $env:DOCKER_TAG"
          helm package $env:CHART_DIR `
            --version $env:CHART_VER `
            --app-version $env:DOCKER_TAG `
            --destination .
        '''
      }
    }

    stage('Publish chart to ChartMuseum (HTTP)') {
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
          $code = & curl.exe -s -w "%{http_code}" -o curl.out -L -X POST --data-binary "@$file" "$env:CHARTMUSEUM_URL/api/charts"
          $icode = [int]$code

          if ($icode -eq 409) {
            Write-Host "Chart version already exists; continuing."
          } elseif ($icode -ge 400) {
            Write-Host "Upload failed with HTTP $icode"
            Get-Content curl.out | Write-Host
            exit 1
          } else {
            Write-Host "Upload OK (HTTP $icode)"
          }
        '''
      }
    }

    stage('Deploy/Upgrade via Helm') {
      steps {
        powershell '''
          $ErrorActionPreference = "Stop"

          # If you previously hit NodePort collisions, either:
          # 1) change your chart to make service.nodePort optional, and/or
          # 2) override below to avoid fixed 30001.
          # Example override (uncomment if your chart supports it):
          # $extra = "--set service.type=NodePort --set service.nodePort=30080"
          $extra = ""

          helm repo remove itay-cm 2>$null
          helm repo add itay-cm $env:CHARTMUSEUM_URL | Out-Null
          helm repo update

          Write-Host "Deploying release $env:RELEASE with image repo $env:DOCKER_IMG tag latest"
          helm upgrade --install $env:RELEASE itay-cm/itaysass-flask `
            --version $env:CHART_VER `
            --set image.repository=$env:DOCKER_IMG `
            --set image.tag=latest `
            $extra

          kubectl rollout status deployment/$env:RELEASE-flask --timeout=120s
        '''
      }
    }
  }

  post {
    always {
      powershell '''
        $ErrorActionPreference = "Continue"
        try {
          kubectl get deploy,svc,hpa,cm,secret -o wide 2>&1 | Write-Host
        } catch {
          Write-Host "kubectl summary failed (non-fatal): $($_.Exception.Message)"
        }
        exit 0
      '''
    }
  }
}
