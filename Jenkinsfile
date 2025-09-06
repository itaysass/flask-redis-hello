pipeline {
  agent any
  options {
    timestamps()
  }

  parameters {
    booleanParam(
      name: 'PRELOAD_TO_MINIKUBE',
      defaultValue: false,
      description: 'If true, preload the built image into Minikube (no registry pull); otherwise pull from Docker Hub.'
    )
  }

  environment {
    DOCKER_IMG  = "itaysass/flask-redis-hello"   // <user>/<repo>
    CHART_DIR   = "helm/itaysass-flask"          // path to chart root
    CHART_VER   = "0.1.2"                        // chart version in Chart.yaml
    RELEASE     = "demo"                         // Helm release name
    // CHARTMUSEUM_URL: resolved dynamically from Minikube
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

          # Start Minikube if needed
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

        # Wait until Service exists and has ports
        $deadline = (Get-Date).AddMinutes(2)
        do {
          try {
            $json = kubectl get svc $svc -n $ns -o json 2>$null
            if ($LASTEXITCODE -eq 0 -and $json) {
              $svcObj = $json | ConvertFrom-Json
              if ($svcObj.spec -and $svcObj.spec.ports -and $svcObj.spec.ports.Count -gt 0) { break }
            }
          } catch { }
          Start-Sleep -Seconds 2
        } while ((Get-Date) -lt $deadline)

        if (-not $svcObj) { throw "Service $ns/$svc not found." }

        $type = $svcObj.spec.type
        $port = $svcObj.spec.ports[0].port
        $nodePort = $svcObj.spec.ports[0].nodePort
        $proto = ($svcObj.spec.ports[0].name -match 'https') ? 'https' : 'http'

        if ($type -eq 'LoadBalancer' -and $svcObj.status.loadBalancer.ingress) {
          # Prefer LoadBalancer if ready
          $ing = $svcObj.status.loadBalancer.ingress[0]
          $host = if ($ing.hostname) { $ing.hostname } else { $ing.ip }
          if (-not $host) { throw "LoadBalancer ingress not ready yet." }
          "$proto://$host:$port"
          exit 0
        }

        # Fallback to NodePort via Minikube node IP
        if (-not $nodePort) { throw "Service type is $type but nodePort is missing. Ensure type=NodePort or expose accordingly." }

        $mkIp = (minikube ip).Trim()
        if (-not $mkIp) { throw "Could not obtain minikube IP." }

        "$proto://$mkIp:$nodePort"
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

              # Write password/token with NO trailing newline, then feed it to docker (avoids newline/encoding quirks)
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

      function Invoke-NonFatal {
        param([string]$Cmd)
        Write-Host "`n>>> $Cmd"
        try {
          # Run the command via PowerShell (lets us pipe to Write-Host safely)
          $out = Invoke-Expression $Cmd
          if ($out -is [System.Array]) { $out = $out -join [Environment]::NewLine }
          if ($out) { Write-Host $out }
        } catch {
          Write-Host "non-fatal: $($_.Exception.Message)"
        } finally {
          # Make sure a native tool's non-zero exit code doesn't bubble up
          $global:LASTEXITCODE = 0
        }
      }

      Invoke-NonFatal 'kubectl get deploy,rs,pod,svc,hpa,cm,secret -o wide 2>&1'
      Invoke-NonFatal 'kubectl get events --sort-by=.lastTimestamp | Select-Object -Last 50 | Out-String'
      Invoke-NonFatal "kubectl describe deploy $env:RELEASE-flask 2>&1 | Out-String"
      Invoke-NonFatal "kubectl logs deploy/$env:RELEASE-flask --all-containers --tail=200 2>&1 | Out-String"

      # Belt & suspenders: ensure PowerShell step returns success
      $global:LASTEXITCODE = 0
      exit 0
    '''
  }
}

}
