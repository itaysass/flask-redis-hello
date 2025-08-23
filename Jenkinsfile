pipeline {
  agent any
  options { timestamps() }

  environment {
    DOCKER_IMG = "itaysass/flask-redis-hello"
    CHART_DIR  = "helm/itaysass-flask"
    CHART_VER  = "0.1.0"
    RELEASE    = "demo"
    CHARTMUSEUM_URL = "http://127.0.0.1:52698"  // <-- set to your actual URL
    KUBECONFIG = "${env.USERPROFILE}\\.kube\\config"
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

    stage('Docker login / build / push') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'dockerhub-creds-2', usernameVariable: 'DH_USER', passwordVariable: 'DH_PASS')]) {
          powershell '''
            Write-Host "Docker login as $env:DH_USER"
            $env:DH_PASS | docker login -u "$env:DH_USER" --password-stdin

            Write-Host "Building image ${env:DOCKER_IMG}:${env:DOCKER_TAG}"
            docker build -f docker/Dockerfile -t ${env:DOCKER_IMG}:${env:DOCKER_TAG} .

            docker tag ${env:DOCKER_IMG}:${env:DOCKER_TAG} ${env:DOCKER_IMG}:latest

            Write-Host "Pushing ${env:DOCKER_IMG}:${env:DOCKER_TAG}"
            docker push ${env:DOCKER_IMG}:${env:DOCKER_TAG}

            Write-Host "Pushing ${env:DOCKER_IMG}:latest"
            docker push ${env:DOCKER_IMG}:latest
          '''
        }
      }
    }

    stage('Helm lint & package chart') {
      steps {
        powershell '''
          helm lint ${env:CHART_DIR}
          helm package ${env:CHART_DIR}
          dir *.tgz
        '''
      }
    }

    stage('Publish chart to ChartMuseum (HTTP)') {
      steps {
        powershell '''
          $file = "itaysass-flask-" + ${env:CHART_VER} + ".tgz"
          if (-not (Test-Path $file)) {
            $file = (Get-ChildItem itaysass-flask-*.tgz | Sort-Object LastWriteTime | Select-Object -Last 1).Name
          }
          Write-Host "Uploading chart: $file to ${env:CHARTMUSEUM_URL}"
          & curl.exe -L -X POST --data-binary "@$file" "${env:CHARTMUSEUM_URL}/api/charts"
        '''
      }
    }

    stage('Deploy/Upgrade via Helm') {
      steps {
        powershell '''
          helm repo add itay-cm ${env:CHARTMUSEUM_URL} | Out-Null
          helm repo update
          Write-Host "Deploying release ${env:RELEASE} with image tag ${env:DOCKER_TAG}"
          helm upgrade --install ${env:RELEASE} itay-cm/itaysass-flask `
            --version ${env:CHART_VER} `
            --set image.tag=${env:DOCKER_TAG}
          kubectl rollout status deployment/${env:RELEASE}-flask --timeout=120s
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
