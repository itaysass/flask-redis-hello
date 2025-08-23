pipeline {
  agent any
  options { timestamps() }

  environment {
    DOCKER_IMG = "itaysass/flask-redis-hello"
    GIT_SHA7   = "${env.GIT_COMMIT?.take(7) ?: 'localdev'}"
    DOCKER_TAG = "${GIT_SHA7}"
    CHART_DIR  = "helm/itaysass-flask"
    CHART_VER  = "0.1.0"
    RELEASE    = "demo"
    CHARTMUSEUM_URL = "http://127.0.0.1:51283"  // <--- set yours
    KUBECONFIG = "${env.USERPROFILE}\\.kube\\config"
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
        powershell 'git rev-parse --short HEAD'
      }
    }

    stage('Docker login / build / push') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'dockerhub-creds', usernameVariable: 'DH_USER', passwordVariable: 'DH_PASS')]) {
          powershell '''
            docker login -u "$env:DH_USER" -p "$env:DH_PASS"
            docker build -f docker/Dockerfile -t ${env.DOCKER_IMG}:${env.DOCKER_TAG} .
            docker tag ${env.DOCKER_IMG}:${env.DOCKER_TAG} ${env.DOCKER_IMG}:latest
            docker push ${env.DOCKER_IMG}:${env.DOCKER_TAG}
            docker push ${env.DOCKER_IMG}:latest
          '''
        }
      }
    }

    stage('Helm lint & package chart') {
      steps {
        powershell '''
          helm lint ${env.CHART_DIR}
          helm package ${env.CHART_DIR}
          dir *.tgz
        '''
      }
    }

    stage('Publish chart to ChartMuseum (HTTP)') {
      steps {
        powershell '''
          $file = "itaysass-flask-" + ${env.CHART_VER} + ".tgz"
          if (-not (Test-Path $file)) {
            $file = (Get-ChildItem itaysass-flask-*.tgz | Sort-Object LastWriteTime | Select-Object -Last 1).Name
          }
          & curl.exe -L -X POST --data-binary "@$file" "${env.CHARTMUSEUM_URL}/api/charts"
        '''
      }
    }

    stage('Deploy/Upgrade via Helm') {
      steps {
        powershell '''
          helm repo add itay-cm ${env.CHARTMUSEUM_URL} | Out-Null
          helm repo update
          helm upgrade --install ${env.RELEASE} itay-cm/itaysass-flask `
            --version ${env.CHART_VER} `
            --set image.tag=${env.DOCKER_TAG}
          kubectl rollout status deployment/${env.RELEASE}-flask --timeout=120s
        '''
      }
    }
  }

  post {
    always {
      powershell '''
        # Don’t fail the build if these commands error
        $ErrorActionPreference = "Continue"

        try {
          kubectl get deploy,svc,hpa,cm,secret -o wide 2>&1 | Write-Host
        } catch {
          Write-Host "kubectl summary failed (non-fatal): $($_.Exception.Message)"
        }

        # Ensure the post step never fails the build
        exit 0
      '''
    }
  }
}
